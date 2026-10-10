from copy import deepcopy
import json
import os
import re
import shutil
import shlex
from typing import Literal, cast
from temporalio import activity, workflow
import asyncio
import tempfile
import semver
from temporalio.exceptions import ApplicationError
from datetime import timedelta
import time

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import (
        Colors,
        format_duration,
        DockerSwarmTask,
        escape_ansi,
        DockerSwarmTaskState,
    )
    from temporal.helpers import empty_folder, exec_cmd_in_server, provision_log
    from temporal.semaphore import AsyncSemaphore

    import docker
    import docker.errors
    from docker.models.services import Service
    from django.conf import settings
    from swarm.models import SwarmNode
    from docker.models.nodes import Node as DockerSwarmNode
    from django.utils import timezone
    from django.db.models import Q

from temporal.constants import (
    DOCKER_CHECK_SCRIPT,
    DOCKER_INSTALL_SCRIPT,
    DOCKER_SYSTEM_INFO_CMD,
    DOCKER_CHECK_OS_SCRIPT,
    SWARM_MANAGER_TCP_PORTS,
    SWARM_WORKER_TCP_PORTS,
    SWARM_UDP_PORTS,
    SWARM_PORT_CHECK_CONTAINER_PREFIX,
    SWARM_PORT_LISTENER_SCRIPT,
    SWARM_PORT_LISTENER_CLEANUP_SCRIPT,
    SWARM_PORT_REACHABLE_SCRIPT,
    SWARM_NODE_SEMAPHORE_KEY,
    SWARM_CLUSTER_SEMAPHORE_KEY,
)

from temporal.shared import (
    NodeSystemInfo,
    OptionalSwarmNodePair,
    SwarmHealthcheckResult,
    SwarmNodeHealthcheckResult,
    SwarmNodePair,
    DeprovisionSwarmNodePayload,
    DockerInstallContext,
    DockerNodeUpdateContext,
    DockerSwarmJoinContext,
    DockerSwarmJoinCredentials,
    DockerSystemInfo,
    SwarmNodePairSSHContext,
    SwarmNodeSSHContext,
    GetSwarmJoinTokenInput,
    DockerSwarmInfo,
    SwarmNodeDetails,
    SwarmNodeServiceHealthcheck,
    SwarmNodeServicesHealthcheckResult,
    SwarmNodeStatusResult,
    DockerNodeHealthCheckContext,
    SimpleClusterSwarmNodeDetails,
)


class SwarmNodeActivities:
    def __init__(self):
        self.docker_client = docker.from_env()

    @staticmethod
    def get_swarm_node_semaphore(node_id: str):
        return AsyncSemaphore(
            key=f"{SWARM_NODE_SEMAPHORE_KEY}-{node_id}",
            limit=1,
            semaphore_timeout=timedelta(minutes=30),
        )

    @staticmethod
    def get_swarm_cluster_semaphore():
        """
        Shared between all provision/deprovision workflows (one slot each),
        the healthcheck acquires all the slots so that it only runs when no workflow is running.
        """
        return AsyncSemaphore(
            key=SWARM_CLUSTER_SEMAPHORE_KEY,
            limit=10,
            semaphore_timeout=timedelta(minutes=30),
        )

    @activity.defn
    async def acquire_swarm_node_semaphore(self, node_id: str):
        """
        Only one provision/deprovision workflow can run on the same node at a time,
        the second one waits for the first to finish.
        """
        if settings.TESTING:
            return  # semaphores are causing issues in testing, blocking execution

        print(f"➡️ Getting node semaphore for {Colors.YELLOW}{node_id}{Colors.ENDC}...")

        # Wait max 10 times with each attempt being 5 secs apart => 50 secs
        result = await self.get_swarm_node_semaphore(node_id).acquire(
            max_retries=10,
            retry_delay=5,
        )
        if not result:
            print(
                f"❌ Failed to get node semaphore for {Colors.YELLOW}{node_id}{Colors.ENDC}."
            )
            raise Exception("Failed to get node semaphore")
        print(f"✅ Got node semaphore for {Colors.YELLOW}{node_id}{Colors.ENDC} !")

        print(
            f"➡️ Getting cluster semaphore for {Colors.YELLOW}{node_id}{Colors.ENDC}..."
        )
        # Wait max 10 times with each attempt being 5 secs apart => 50 secs
        result = await self.get_swarm_cluster_semaphore().acquire(
            max_retries=10,
            retry_delay=5,
        )
        if not result:
            print(
                f"❌ Failed to get cluster semaphore for {Colors.YELLOW}{node_id}{Colors.ENDC}."
            )
            raise Exception("Failed to get cluster semaphore")
        print(f"✅ Got cluster semaphore for {Colors.YELLOW}{node_id}{Colors.ENDC} !")

    @activity.defn
    async def release_swarm_node_semaphore(self, node_id: str):
        if settings.TESTING:
            return  # semaphores are causing issues in testing, blocking execution
        await self.get_swarm_cluster_semaphore().release()
        await self.get_swarm_node_semaphore(node_id).release()

    @activity.defn
    async def lock_swarm_healthcheck_semaphore(self) -> bool:
        """
        Returns `False` if a provision/deprovision workflow is running, the healthcheck should be skipped.
        """
        if settings.TESTING:
            return True  # semaphores are causing issues in testing, blocking execution
        return await self.get_swarm_cluster_semaphore().acquire_all(max_retries=1)

    @activity.defn
    async def reset_swarm_healthcheck_semaphore(self):
        if settings.TESTING:
            return  # semaphores are causing issues in testing, blocking execution
        await self.get_swarm_cluster_semaphore().reset()

    @activity.defn
    async def prepare_node_provision(self, node: SwarmNodeDetails) -> str:
        await provision_log(
            node,
            [
                f"",
                f"",
                f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                f"➡️ Preparing node provisioning for server {Colors.ORANGE}{node.private_ip}{Colors.ENDC}...",
            ],
        )
        updated = await SwarmNode.objects.filter(
            id=node.id,
            is_initial_install_server=False,
            status__in=[
                SwarmNode.Status.CREATED,
                SwarmNode.Status.FAILED,
                SwarmNode.Status.REMOVED,
            ],
        ).aupdate(
            status=SwarmNode.Status.PROVISIONING,
            status_message=None,
            swarm_node_id=None,
            last_status_update=timezone.now(),
        )
        if updated == 0:
            raise ApplicationError(
                "Cannot provision a nonexistent or active node.",
                non_retryable=True,
            )
        return SwarmNode.Status.PROVISIONING

    @activity.defn
    async def prepare_node_deprovision(self, node: SwarmNodeDetails) -> str:
        await provision_log(
            node,
            [
                f"",
                f"",
                f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                f"➡️ Preparing node deprovisioning for server {Colors.ORANGE}{node.private_ip}{Colors.ENDC}...",
            ],
        )
        swarm_node = await SwarmNode.objects.filter(
            id=node.id,
            is_initial_install_server=False,
            status__in=[
                SwarmNode.Status.ACTIVE,
                SwarmNode.Status.DOWN,
                SwarmNode.Status.PAUSED,
                SwarmNode.Status.DRAINED,
                SwarmNode.Status.UNHEALTHY,
            ],
        ).afirst()

        if swarm_node is None:
            raise ApplicationError(
                "Cannot deprovision a nonexistent node or a node that is not part of the cluster.",
                non_retryable=True,
            )

        # clear the message of any previous run
        swarm_node.status_message = None
        await swarm_node.asave(update_fields=["status_message", "updated_at"])
        return swarm_node.status

    @activity.defn
    async def prepare_node_for_update(self, node: SimpleClusterSwarmNodeDetails):
        await provision_log(
            node,
            [
                f"",
                f"",
                f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                f"➡️ Preparing node update for server {Colors.ORANGE}{node.private_ip}{Colors.ENDC}...",
            ],
        )

        swarm_node = await SwarmNode.objects.filter(
            id=node.id,
            swarm_node_id__isnull=False,
            status__in=[
                SwarmNode.Status.ACTIVE,
                SwarmNode.Status.DOWN,
                SwarmNode.Status.PAUSED,
                SwarmNode.Status.DRAINED,
                SwarmNode.Status.UNHEALTHY,
            ],
        ).afirst()

        if swarm_node is None:
            raise ApplicationError(
                "Cannot update a nonexistent node or a node that is not part of the cluster.",
                non_retryable=True,
            )

        # clear the message of any previous run
        swarm_node.status_message = None
        await swarm_node.asave(update_fields=["status_message", "updated_at"])
        return swarm_node.swarm_node_id

    @activity.defn
    async def create_ssh_keys_temp_dir(self, payload: OptionalSwarmNodePair):
        await provision_log(
            payload.target_node,
            [
                "",
                "➡️ Creating temporary folder for SSH key...",
            ],
        )
        temp_dir = tempfile.mkdtemp()
        await provision_log(
            payload.target_node,
            f"✅ Temporary folder created at {Colors.ORANGE}{temp_dir}{Colors.ENDC}",
        )

        await provision_log(payload.target_node, "Emptying temporary folder...")
        await asyncio.to_thread(empty_folder, temp_dir)
        await provision_log(payload.target_node, "✅ Temporary emptyed")

        await provision_log(
            payload.target_node,
            [
                "",
                f"➡️ Writing SSH Keys into  {Colors.ORANGE}{temp_dir}{Colors.ENDC}...",
            ],
        )

        if payload.main_node:
            main_node_key_location = os.path.join(
                temp_dir, f"{payload.main_node.id}.key"
            )
            with open(
                main_node_key_location,
                "w",
            ) as file:
                file.write(payload.main_node.ssh_key)
                await provision_log(
                    payload.target_node,
                    f"✅ Wrote ssh key for the main node - {Colors.BLUE}{payload.main_node.private_ip}{Colors.ENDC} at {Colors.ORANGE}{main_node_key_location}{Colors.ENDC}",
                )
            await provision_log(
                payload.target_node,
                f"Adjusting ssh key permissions for {Colors.ORANGE}{main_node_key_location}{Colors.ENDC}",
            )
            os.chmod(main_node_key_location, 0o600)
            await provision_log(payload.target_node, f"✅ Done")

        new_node_key_location = os.path.join(temp_dir, f"{payload.target_node.id}.key")
        with open(new_node_key_location, "w") as file:
            file.write(payload.target_node.ssh_key)
            await provision_log(
                payload.target_node,
                f"✅ Wrote ssh key for the target node - {Colors.BLUE}{payload.target_node.private_ip}{Colors.ENDC} at {Colors.ORANGE}{new_node_key_location}{Colors.ENDC}",
            )
        await provision_log(
            payload.target_node,
            f"Adjusting ssh key permissions for {Colors.ORANGE}{new_node_key_location}{Colors.ENDC}",
        )
        os.chmod(new_node_key_location, 0o600)
        await provision_log(payload.target_node, f"✅ Done")

        return temp_dir

    @activity.defn
    async def finish_and_save_node_provisioning(self, result: SwarmNodeStatusResult):
        try:
            node = await SwarmNode.objects.filter(id=result.id).aget()

            node.status = result.status
            node.status_message = (
                escape_ansi(result.status_message)
                if result.status_message is not None
                else None
            )
            node.services = {  # type: ignore
                svc.service_name: {
                    "message": svc.message,
                    "status": svc.status,
                }
                for svc in result.services.values()
            }
            if result.docker_info:
                node.cpus = result.docker_info.NCPU
                node.memory_bytes = result.docker_info.MemTotal
                node.docker_version = result.docker_info.ServerVersion
            if result.swarm_hostname:
                node.hostname = result.swarm_hostname
            if result.architecture:
                node.architecture = result.architecture
            if result.docker_info is not None and result.docker_info.Swarm is not None:
                node.swarm_node_id = result.docker_info.Swarm.NodeID

            await node.asave(
                update_fields=[
                    "updated_at",
                    "status",
                    "status_message",
                    "cpus",
                    "services",
                    "memory_bytes",
                    "docker_version",
                    "architecture",
                    "hostname",
                    "swarm_node_id",
                    "last_status_update",
                ]
            )

            if result.status == SwarmNode.Status.FAILED:
                await provision_log(
                    result,
                    [
                        f"",
                        f"",
                        f"❌  Node provisioning finished with status {Colors.RED}{result.status}{Colors.ENDC}",
                        f"    {Colors.RED}{result.status_message}{Colors.ENDC}",
                        f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                    ],
                    error=True,
                )

            else:
                await provision_log(
                    result,
                    [
                        f"",
                        f"",
                        f"✅ Node provisioning finished with status {Colors.GREEN}{result.status}{Colors.ENDC}",
                        f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                    ],
                )

        except SwarmNode.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent node.",
                non_retryable=True,
            )

    @activity.defn
    async def finish_and_save_node_deprovisioning(self, result: SwarmNodeStatusResult):
        if result.status == SwarmNode.Status.REMOVED:
            # The node is not part of the cluster anymore, so its swarm attributes are not valid
            updated = await SwarmNode.objects.filter(id=result.id).aupdate(
                status=result.status,
                status_message=(
                    escape_ansi(result.status_message)
                    if result.status_message is not None
                    else None
                ),
                swarm_node_id=None,
                hostname=None,
                docker_version=None,
                architecture=None,
                cpus=None,
                memory_bytes=None,
                last_status_update=timezone.now(),
            )
        else:
            updated = await SwarmNode.objects.filter(id=result.id).aupdate(
                status=result.status,
                status_message=(
                    escape_ansi(result.status_message)
                    if result.status_message is not None
                    else None
                ),
                last_status_update=timezone.now(),
            )

        if updated == 0:
            raise ApplicationError(
                "Cannot save a non existent node.",
                non_retryable=True,
            )

        if result.status == SwarmNode.Status.REMOVED:
            await provision_log(
                result,
                [
                    f"",
                    f"",
                    f"✅ Node deprovisioning finished with status {Colors.GREY}{result.status}{Colors.ENDC}",
                    f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                ],
            )
        else:
            await provision_log(
                result,
                [
                    f"",
                    f"",
                    f"❌  Node deprovisioning failed, the node is still part of the cluster with status {Colors.RED}{result.status}{Colors.ENDC}",
                    f"    {Colors.RED}{result.status_message}{Colors.ENDC}",
                    f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
                ],
                error=True,
            )

    @activity.defn
    async def test_ssh_connection(self, ctx: SwarmNodeSSHContext):
        node = ctx.node
        await provision_log(
            ctx.target_node or node,
            f"➡️ Testing SSH Connection to server {Colors.ORANGE}{node.private_ip}{Colors.ENDC} over port {Colors.ORANGE}{node.ssh_port}{Colors.ENDC}...",
        )
        exit_code, _ = await exec_cmd_in_server(ctx, cmd="exit 0")

        if exit_code == 0:
            await provision_log(
                ctx.target_node or node,
                f"✅ Connection to server {Colors.ORANGE}{node.private_ip}{Colors.ENDC} over port {Colors.ORANGE}{node.ssh_port}{Colors.ENDC} is possible",
            )
        else:
            msg = f"❌ Connection to server {Colors.ORANGE}{node.private_ip}{Colors.ENDC} over port {Colors.ORANGE}{node.ssh_port}{Colors.ENDC} is NOT possible"
            await provision_log(
                ctx.target_node or node,
                msg,
                error=True,
            )
            raise ApplicationError(message=msg, non_retryable=True)

    @activity.defn
    async def check_os_and_arch_compatibility(
        self, ctx: SwarmNodeSSHContext
    ) -> NodeSystemInfo:
        os_info: str | None = None
        arch: str | None = None

        async def message_handler(message: str):
            nonlocal os_info, arch
            await provision_log(ctx.node, f"{Colors.GREY}{message}{Colors.ENDC}")

            os_pattern_match = re.compile(r"^os=([^\s]*)$").match(message)
            if os_pattern_match:
                os_info = str(os_pattern_match.groups(1)[0])

            arch_pattern_match = re.compile(r"^arch=([^\s]*)$").match(message)
            if arch_pattern_match:
                arch = str(arch_pattern_match.groups(1)[0])

        await provision_log(
            ctx.node,
            [
                "",
                f"➡️ Checking supported OS information and system architecture...",
            ],
        )
        exit_code, _ = await exec_cmd_in_server(
            ctx,
            cmd=DOCKER_CHECK_OS_SCRIPT,
            output_handler=message_handler,
        )
        if exit_code != 0 or os_info is None or arch is None:
            message = f"❌ {Colors.RED}Failed to get supported OS distribution in server {Colors.BLUE}{ctx.node.private_ip}{Colors.ENDC}"
            await provision_log(ctx.node, message, error=True)
            raise ApplicationError(message=message, non_retryable=True)

        await provision_log(
            ctx.node,
            f"✅ Detected supported OS distribution: {Colors.ORANGE}{os_info}{Colors.ENDC}",
        )

        # The main server is the one running ZaneOps, so we can query docker directly
        main_arch: str = self.docker_client.info()["Architecture"]
        if arch != main_arch:
            message = (
                f"❌ {Colors.RED}Server {Colors.BLUE}{ctx.node.private_ip}{Colors.RED} has the architecture {Colors.ORANGE}{arch}{Colors.RED}, "
                f"but the main server uses {Colors.ORANGE}{main_arch}{Colors.RED}. All servers in the cluster must have the same architecture.{Colors.ENDC}"
            )
            await provision_log(ctx.node, message, error=True)
            raise ApplicationError(message=message, non_retryable=True)

        await provision_log(
            ctx.node,
            f"✅ Server architecture {Colors.ORANGE}{arch}{Colors.ENDC} matches the main server",
        )
        return NodeSystemInfo(os=os_info, architecture=arch)

    @activity.defn
    async def check_docker_installation(
        self, ctx: SwarmNodeSSHContext
    ) -> DockerSystemInfo | None:
        async def message_handler(message: str):
            system_info: DockerSystemInfo | None = None
            try:
                parsed_data = json.loads(message)
            except json.JSONDecodeError:
                # Invalid JSON, not the data we are looking for
                pass
            else:
                system_info = DockerSystemInfo.from_dict(parsed_data)
            finally:
                await provision_log(
                    ctx.node,
                    f"{Colors.GREY}{message}{Colors.ENDC}",
                )

            return system_info

        await provision_log(
            ctx.target_node or ctx.node,
            [
                "",
                f"➡️ Checking existing Docker installation on server {Colors.ORANGE}{ctx.node.private_ip}{Colors.ENDC}...",
            ],
        )
        exit_code, result = await exec_cmd_in_server(
            ctx, cmd=DOCKER_CHECK_SCRIPT, output_handler=message_handler
        )
        if exit_code == 0 and result is not None:
            await provision_log(
                ctx.target_node or ctx.node,
                f"✅ Found Docker installation with version {Colors.ORANGE}{result.ServerVersion}{Colors.ENDC}",
            )
            return result
        else:
            await provision_log(
                ctx.target_node or ctx.node,
                f"❌ Docker is not installed on this server",
                error=True,
            )

        return None

    @activity.defn
    async def get_main_node_docker_info(
        self, payload: SwarmNodePair
    ) -> DockerSystemInfo:
        await provision_log(
            payload.target_node,
            [
                "",
                f"➡️ Checking Docker installation on the main server {Colors.ORANGE}{payload.main_node.private_ip}{Colors.ENDC}...",
            ],
        )
        try:
            info = DockerSystemInfo.from_dict(self.docker_client.info())
        except docker.errors.DockerException as e:
            await provision_log(
                payload.target_node,
                f"❌ Failed to get Docker info on the main server: {Colors.RED}{e}{Colors.ENDC}",
                error=True,
            )
            raise ApplicationError(
                message=f"❌ Failed to get Docker info on the main server {payload.main_node.private_ip}, provisionning cannot continue.",
                non_retryable=True,
            )

        await provision_log(
            payload.target_node,
            f"✅ Found Docker installation with version {Colors.ORANGE}{info.ServerVersion}{Colors.ENDC} on the main server",
        )
        return info

    @activity.defn
    async def install_docker_on_node(
        self, ctx: DockerInstallContext
    ) -> DockerSystemInfo:
        await provision_log(
            ctx.node,
            [
                "",
                f"➡️ Setting up Docker {Colors.ORANGE}v{ctx.version_to_install}{Colors.ENDC} (same version as the main server) on server {Colors.BLUE}{ctx.node.private_ip}{Colors.ENDC}...",
            ],
        )
        if (
            ctx.info is not None
            # Check that docker version is already the same
            and semver.compare(ctx.info.ServerVersion, ctx.version_to_install) == 0
        ):
            await provision_log(
                ctx.node,
                f"⏩ Docker {Colors.ORANGE}v{ctx.info.ServerVersion}{Colors.ENDC} already installed on server, skipping installation",
            )
            return ctx.info

        async def message_handler(message: str):
            await provision_log(ctx.node, f"{Colors.GREY}{message}{Colors.ENDC}")
            system_info: DockerSystemInfo | None = None
            try:
                parsed_data = json.loads(message)
            except json.JSONDecodeError:
                # Invalid JSON, not the data we are looking for
                pass
            else:
                system_info = DockerSystemInfo.from_dict(parsed_data)
            return system_info

        await provision_log(
            ctx.node,
            f"Docker is missing or has a different version, installing Docker {Colors.ORANGE}v{ctx.version_to_install}{Colors.ENDC}...",
        )
        exit_code, result = await exec_cmd_in_server(
            ctx,
            cmd=DOCKER_INSTALL_SCRIPT.format(
                version=shlex.quote(ctx.version_to_install)
            ),
            output_handler=message_handler,
        )

        if exit_code == 0 and result is not None:
            # Alpine & Arch packages cannot be pinned, they install the version provided by the distribution
            if result.ServerVersion != ctx.version_to_install:
                message = (
                    f"❌ {Colors.RED}Installed Docker v{result.ServerVersion} on server {Colors.BLUE}{ctx.node.private_ip}{Colors.RED}, "
                    f"but the main server uses Docker v{ctx.version_to_install}{Colors.ENDC}"
                )
                await provision_log(ctx.node, message, error=True)
                raise ApplicationError(message=message, non_retryable=True)

            await provision_log(
                ctx.node,
                f"✅ Succesfully Installed Docker {Colors.ORANGE}v{result.ServerVersion}{Colors.ENDC}",
            )
            return result

        message = f"❌ {Colors.RED}Failed to install docker on server {Colors.BLUE}{ctx.node.private_ip}{Colors.ENDC}"
        await provision_log(ctx.node, message, error=True)
        raise ApplicationError(message=message, non_retryable=True)

    @activity.defn
    async def check_swarm_ports_reachability(self, ctx: SwarmNodePairSSHContext):
        main_node = ctx.pair.main_node
        target_node = ctx.pair.target_node
        main_ctx = SwarmNodeSSHContext(node=main_node, tmp_dir=ctx.tmp_dir)
        target_ctx = SwarmNodeSSHContext(node=target_node, tmp_dir=ctx.tmp_dir)

        target_ports = (
            SWARM_MANAGER_TCP_PORTS
            if target_node.swarm_role == "MANAGER"
            else SWARM_WORKER_TCP_PORTS
        )
        unreachable: list[str] = []

        await provision_log(
            target_node,
            [
                "",
                f"➡️ Running port reachability checks...",
            ],
        )

        async def check_port(
            source_ctx: SwarmNodeSSHContext, destination_ip: str, port: int
        ):
            await provision_log(
                target_node,
                f"Checking that {Colors.BLUE}{source_ctx.node.private_ip}{Colors.ENDC} can reach {Colors.BLUE}{destination_ip}:{port}/tcp{Colors.ENDC}...",
            )
            exit_code, _ = await exec_cmd_in_server(
                source_ctx,
                cmd=SWARM_PORT_REACHABLE_SCRIPT.format(ip=destination_ip, port=port),
            )
            if exit_code == 0:
                await provision_log(
                    target_node,
                    f"✅ {Colors.BLUE}{destination_ip}:{port}/tcp{Colors.ENDC} is reachable",
                )
            else:
                await provision_log(
                    target_node,
                    f"❌ {Colors.RED}{Colors.BLUE}{destination_ip}:{port}/tcp{Colors.ENDC} is NOT reachable from {source_ctx.node.private_ip}{Colors.ENDC}",
                    error=True,
                )
                unreachable.append(
                    f"{source_ctx.node.private_ip} -> {destination_ip}:{port}/tcp"
                )

        # The manager is already listening on its swarm ports
        for port in SWARM_MANAGER_TCP_PORTS:
            await check_port(target_ctx, main_node.private_ip, port)

        # Nothing listens on the target node yet, so we start temporary listeners
        try:
            for port in target_ports:
                exit_code, _ = await exec_cmd_in_server(
                    target_ctx,
                    cmd=SWARM_PORT_LISTENER_SCRIPT.format(
                        container=f"{SWARM_PORT_CHECK_CONTAINER_PREFIX}-{port}",
                        port=port,
                    ),
                )
                if exit_code != 0:
                    raise ApplicationError(
                        message=f"Failed to start a temporary listener on port {port} in server {target_node.private_ip}",
                    )

            for port in target_ports:
                await check_port(main_ctx, target_node.private_ip, port)
        finally:
            await exec_cmd_in_server(target_ctx, cmd=SWARM_PORT_LISTENER_CLEANUP_SCRIPT)

        await provision_log(
            target_node,
            f"⚠️ {Colors.YELLOW}UDP ports {', '.join(f'{p}/udp' for p in SWARM_UDP_PORTS)} cannot be checked, "
            f"make sure they are open between {main_node.private_ip} and {target_node.private_ip}{Colors.ENDC}",
        )

        if unreachable:
            raise ApplicationError(
                message=f"Swarm ports are not reachable: {', '.join(unreachable)}",
                non_retryable=True,
            )

    @activity.defn
    async def get_swarm_join_token(
        self, ctx: GetSwarmJoinTokenInput
    ) -> DockerSwarmJoinCredentials:
        async def message_handler(message: str):
            if message.strip().startswith("docker swarm join --token"):
                result = [
                    credential.strip()
                    for credential in message.replace(
                        "docker swarm join --token", ""
                    ).split()
                    if credential.strip()
                ]

                if len(result) == 2:
                    return result[0], result[1]  # token, manager IP
            # Print other message than the join token credentials
            await provision_log(
                ctx.target_node or ctx.node, f"{Colors.GREY}{message}{Colors.ENDC}"
            )

        await provision_log(
            ctx.target_node or ctx.node,
            [
                "",
                f"➡️ Geting Docker swarm Join Token credentials...",
            ],
        )
        exit_code, result = await exec_cmd_in_server(
            ctx,
            cmd=f"docker swarm join-token {ctx.swarm_role.lower()}",
            output_handler=message_handler,
        )
        if exit_code == 0 and result is not None:
            token = result[0]
            credentials = DockerSwarmJoinCredentials(
                token=token,
                manager_addr=result[1],
            )
            obfuscated_token = (
                token[:9] + "*" * 12 + token[-4:]
            )  # first 9 chars + 12 stars + last 4 chars, will print something like this: `SWMTKN-1-************37ug`
            await provision_log(
                ctx.target_node or ctx.node,
                [
                    f"✅ Got Swarm Join Token credentials:",
                    f"{Colors.GREY}docker swarm join --token {obfuscated_token} {credentials.manager_addr}{Colors.ENDC}",
                ],
            )
            return credentials

        message = (
            f"❌ {Colors.RED}Failed to get Swarm Join Token credentials{Colors.ENDC}"
        )
        await provision_log(
            ctx.node,
            message,
            error=True,
        )
        raise ApplicationError(message, non_retryable=True)

    @activity.defn
    async def join_swarm_cluster(self, ctx: DockerSwarmJoinContext) -> DockerSwarmInfo:
        info = ctx.info
        node = ctx.node
        credentials = ctx.credentials
        await provision_log(
            node,
            [
                "",
                f"➡️ Joining server {Colors.BLUE}{node.private_ip}{Colors.ENDC} to docker swarm cluster from manager {Colors.BLUE}{credentials.manager_addr}{Colors.ENDC}...",
            ],
        )
        if info.Swarm is not None:
            if (
                any(
                    [
                        manager.Addr == credentials.manager_addr
                        for manager in info.Swarm.RemoteManagers
                    ]
                )
                and info.Swarm.role == node.swarm_role
            ):
                await provision_log(
                    node,
                    f"⏩ Server is already part of the swarm cluster with the {Colors.ORANGE}{node.swarm_role}{Colors.ENDC} with ID {Colors.ORANGE}{info.Swarm.NodeID}{Colors.ENDC}, skipping join",
                )
                return info.Swarm

        async def message_handler(message: str):
            system_info: DockerSystemInfo | None = None
            try:
                parsed_data = json.loads(message)
            except json.JSONDecodeError:
                # Invalid JSON, not the data we are looking for
                pass
            else:
                system_info = DockerSystemInfo.from_dict(parsed_data)

            await provision_log(
                node,
                f"{Colors.GREY}{message}{Colors.ENDC}",
            )
            return system_info

        exit_code, result = await exec_cmd_in_server(
            ctx,
            cmd=f"docker swarm join --advertise-addr {node.private_ip} --token {credentials.token} {credentials.manager_addr} && {DOCKER_SYSTEM_INFO_CMD}",
            output_handler=message_handler,
        )
        if exit_code == 0 and result is not None and result.Swarm is not None:
            await provision_log(
                node,
                f"✅ Server {Colors.BLUE}{node.private_ip}{Colors.ENDC} joined the cluster as a {Colors.BLUE}{node.swarm_role.lower()}{Colors.ENDC} with ID {Colors.ORANGE}{result.Swarm.NodeID}{Colors.ENDC}",
            )
            return result.Swarm

        message = f"❌ {Colors.RED}Failed to add server {Colors.BLUE}{node.private_ip}{Colors.ENDC} swarm cluster{Colors.ENDC}"
        await provision_log(
            node,
            message,
            error=True,
        )
        raise ApplicationError(message, non_retryable=True)

    @activity.defn
    async def update_node_labels(self, ctx: DockerNodeUpdateContext):
        info = ctx.swarm_info
        node = ctx.node
        await provision_log(
            node,
            [
                "",
                f"➡️ Updating labels for swarm node {Colors.BLUE}{info.NodeID}{Colors.ENDC}...",
            ],
        )
        try:
            swarm_node: DockerSwarmNode = self.docker_client.nodes.get(info.NodeID)
            original_spec = swarm_node.attrs["Spec"]

            new_spec = deepcopy(original_spec)

            labels = new_spec.get("Labels", {})
            if SwarmNode.ClusterRole.APP_SERVER in node.cluster_roles:
                labels[settings.APP_SERVER_LABEL] = "true"
            if SwarmNode.ClusterRole.BUILD_SERVER in node.cluster_roles:
                labels[settings.BUILD_SERVER_LABEL] = "true"

            new_spec["Role"] = node.swarm_role.lower()
            new_spec["Labels"] = labels
            swarm_node.update(new_spec)
        except docker.errors.APIError:
            msg = f"❌ {Colors.RED}Failed to update swarm labels {info.NodeID}{Colors.ENDC}"
            await provision_log(
                node,
                msg,
                error=True,
            )
            raise ApplicationError(msg, non_retryable=True)
        else:
            await provision_log(
                node,
                f"✅ Succesfully updated labels for Swarm Node {Colors.BLUE}{info.NodeID}{Colors.ENDC}",
            )

        return swarm_node.attrs["Description"]["Hostname"]

    @activity.defn
    async def update_swarm_node_in_cluster(
        self, node: SimpleClusterSwarmNodeDetails
    ) -> str:
        await provision_log(
            node,
            [
                "",
                f"➡️ Updating node {Colors.BLUE}{node.private_ip} (node id: {node.swarm_node_id}){Colors.ENDC} in docker swarm cluster...",
            ],
        )
        try:
            swarm_node: DockerSwarmNode = self.docker_client.nodes.get(
                node.swarm_node_id
            )
            original_spec = swarm_node.attrs["Spec"]

            new_spec = deepcopy(original_spec)

            labels: dict = new_spec.get("Labels", {})

            # Remove labels first before readding
            labels.pop(settings.APP_SERVER_LABEL, None)
            labels.pop(settings.BUILD_SERVER_LABEL, None)

            if SwarmNode.ClusterRole.APP_SERVER in node.cluster_roles:
                labels[settings.APP_SERVER_LABEL] = "true"
            if SwarmNode.ClusterRole.BUILD_SERVER in node.cluster_roles:
                labels[settings.BUILD_SERVER_LABEL] = "true"

            new_spec["Role"] = (
                "manager" if node.is_initial_install_server else node.swarm_role.lower()
            )  # Cannot set the main server role lower than manager

            new_spec["Labels"] = labels
            swarm_node.update(new_spec)
        except docker.errors.APIError:
            msg = f"❌ {Colors.RED}Failed to update node {node.swarm_node_id} in docker swarm cluster{Colors.ENDC}"
            await provision_log(
                node,
                msg,
                error=True,
            )
            raise ApplicationError(msg, non_retryable=True)
        else:
            await provision_log(
                node,
                f"✅ Succesfully updated Node {Colors.BLUE}{node.private_ip} (node id: {node.swarm_node_id}){Colors.ENDC} in docker swarm cluster",
            )

        return swarm_node.attrs["Description"]["Hostname"]

    @activity.defn
    async def save_updated_swarm_node(self, node: SimpleClusterSwarmNodeDetails):
        updated = await SwarmNode.objects.filter(
            id=node.id,
            status__in=[
                SwarmNode.Status.ACTIVE,
                SwarmNode.Status.DOWN,
                SwarmNode.Status.PAUSED,
                SwarmNode.Status.DRAINED,
                SwarmNode.Status.UNHEALTHY,
            ],
        ).aupdate(
            swarm_role=SwarmNode.Role.MANAGER
            if node.is_initial_install_server
            else node.swarm_role,
            cluster_roles=node.cluster_roles,
        )
        if updated == 0:
            raise ApplicationError(
                "Cannot save a non existent node.",
                non_retryable=True,
            )

        await provision_log(
            node,
            [
                f"",
                f"",
                f"✅ Node updated succesfully",
                f"{Colors.GREY}=========================================================================================={Colors.ENDC}",
            ],
        )

    @activity.defn
    async def run_swarm_node_services_healthcheck(
        self, ctx: DockerNodeHealthCheckContext
    ) -> SwarmNodeServicesHealthcheckResult:
        info = ctx.swarm_info
        node = ctx.node

        try:
            node_object = await SwarmNode.objects.filter(id=node.id).aget()
        except SwarmNode.DoesNotExist:
            raise ApplicationError(
                "Cannot check a status of a non existent swarm node.",
                non_retryable=True,
            )

        result = SwarmNodeServicesHealthcheckResult()

        await provision_log(
            node,
            [
                "",
                f"➡️ Waiting for the ZaneOps services to be running on swarm node {Colors.BLUE}{info.NodeID}{Colors.ENDC}...",
            ],
        )

        services = self.docker_client.services.list(
            filters={
                "label": ["com.docker.stack.namespace=zane"],
                "mode": "global",  # Check global services that should run on this node
            },
        )

        if SwarmNode.ClusterRole.BUILD_SERVER not in node.cluster_roles:
            services = [
                svc
                for svc in services
                if svc.attrs["Spec"].get("Labels", {}).get("zane.role")
                != "build-worker"
            ]  # ignore build worker for app-only servers

        healthcheck_timeout = timedelta(minutes=3).total_seconds()

        async def sync_latest_task_status(
            service: Service,
            tasks: list[DockerSwarmTask],
        ):
            most_recent_swarm_task = None
            if len(tasks) > 0:
                most_recent_swarm_task = max(
                    tasks,
                    key=lambda task: task.Version.Index,
                )
                result.services[service.name] = SwarmNodeServiceHealthcheck(
                    service_name=service.name,
                    status=most_recent_swarm_task.Status.State.value,
                    message=most_recent_swarm_task.Status.Message,
                )
                node_object.services = {  # type: ignore
                    svc.service_name: {
                        "message": svc.message,
                        "status": svc.status,
                    }
                    for svc in result.services.values()
                }
                await node_object.asave(update_fields=["services", "updated_at"])
            return most_recent_swarm_task

        async def wait_for_swarm_service_to_be_updated(service: Service):
            print(
                f"Waiting for service `{Colors.BLUE}{service.name=}{Colors.ENDC}` to be updated..."
            )
            start_time = time.monotonic()
            time_left = healthcheck_timeout

            filters = {"node": info.NodeID, "desired-state": "running"}
            task_list = [
                DockerSwarmTask.from_dict(task)
                for task in service.tasks(filters=filters)
            ]
            latest_task = await sync_latest_task_status(service, task_list)

            while time_left >= 1 and (
                latest_task is None
                or latest_task.Status.State != DockerSwarmTaskState.RUNNING
            ):
                print(
                    f"Swarm service {Colors.BLUE}{service.name}{Colors.ENDC} is not updated, "
                    + f"| retrying in {Colors.ORANGE}{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}s{Colors.ENDC}"
                    + f"| healthcheck_time_left={Colors.ORANGE}{format_duration(time_left)}{Colors.ENDC}..."
                )
                await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)

                time_left = healthcheck_timeout - (time.monotonic() - start_time)

                task_list = [
                    DockerSwarmTask.from_dict(task)
                    for task in service.tasks(filters=filters)
                ]
                latest_task = await sync_latest_task_status(service, task_list)

            successful = (
                latest_task is not None
                and latest_task.Status.State == DockerSwarmTaskState.RUNNING
            )
            if successful:
                print(
                    f"✅ Succesfuly updated swarm service {Colors.BLUE}{service.name}{Colors.ENDC}"
                )
            return successful

        services_updated = all(
            await asyncio.gather(
                *[wait_for_swarm_service_to_be_updated(service) for service in services]
            )
        )

        if services_updated:
            await provision_log(
                node,
                f"✅ ZaneOps services are running on swarm node {Colors.BLUE}{info.NodeID}{Colors.ENDC}",
            )
        else:
            await provision_log(
                node,
                f"⚠️ {Colors.ORANGE}ZaneOps services are not running yet on swarm node {Colors.BLUE}{info.NodeID}{Colors.ORANGE} "
                f"after {Colors.GREY}{format_duration(healthcheck_timeout)}{Colors.ENDC}, they may still be starting. "
                f"The server status will be updated by the next healthcheck.{Colors.ENDC}",
            )

        return result

    @activity.defn
    async def delete_ssh_keys_temp_dir(self, ctx: SwarmNodeSSHContext):
        await provision_log(
            ctx.node,
            [
                "",
                f"➡️ Deleting temporary folder for SSH keys {Colors.ORANGE}{ctx.tmp_dir}{Colors.ENDC}...",
            ],
        )
        shutil.rmtree(ctx.tmp_dir, ignore_errors=True)
        await provision_log(
            ctx.node,
            [
                "✅ Temporary folder for SSH keys deleted",
            ],
        )

    @activity.defn
    async def drain_swarm_node_and_remove_labels(
        self, payload: DeprovisionSwarmNodePayload
    ) -> Literal["DRAINED", "NOT_IN_SWARM"]:
        target_node = payload.target_node
        await provision_log(
            target_node,
            [
                "",
                f"➡️ Draining swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ENDC}...",
            ],
        )
        try:
            swarm_node = self.docker_client.nodes.get(target_node.swarm_node_id)
        except docker.errors.NotFound:
            await provision_log(
                target_node,
                f"⚠️ {Colors.ORANGE}Swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ORANGE} was not found in the cluster, "
                f"it may have already been removed. Skipping drain.{Colors.ENDC}",
            )
            return "NOT_IN_SWARM"

        new_spec = deepcopy(swarm_node.attrs["Spec"])
        # Removing ZaneOps labels
        cast(dict, new_spec["Labels"]).pop(settings.APP_SERVER_LABEL, None)
        cast(dict, new_spec["Labels"]).pop(settings.BUILD_SERVER_LABEL, None)
        new_spec["Availability"] = "drain"
        # Demote swarm node to worker when removing
        new_spec["Role"] = "worker"

        # Other docker errors are raised so that the activity is retried
        swarm_node.update(new_spec)

        await provision_log(
            target_node,
            f"✅ Swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ENDC} drained and labels removed, no new tasks will be scheduled on it",
        )
        return "DRAINED"

    @activity.defn
    async def wait_for_global_services_to_be_drained(
        self, payload: DeprovisionSwarmNodePayload
    ):
        target_node = payload.target_node
        await provision_log(
            target_node,
            [
                "",
                f"➡️ Waiting for the ZaneOps services to be removed from swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ENDC}...",
            ],
        )

        services = self.docker_client.services.list(
            filters={
                "label": ["com.docker.stack.namespace=zane"],
                "mode": "global",  # Only global services have tasks on every node
            },
        )

        healthcheck_timeout = timedelta(minutes=3).total_seconds()

        async def wait_for_swarm_service_to_be_drained(service: Service):
            try:
                print(
                    f"Waiting for service `{Colors.BLUE}{service.name=}{Colors.ENDC}` to be drained..."
                )
                start_time = time.monotonic()
                time_left = healthcheck_timeout

                filters = {
                    "node": target_node.swarm_node_id,
                    "desired-state": "running",
                }
                task_list: list = service.tasks(filters=filters)

                while len(task_list) > 0 and time_left >= 1:
                    print(
                        f"Swarm service {Colors.BLUE}{service.name}{Colors.ENDC} is not drained, "
                        + f"| retrying in {Colors.ORANGE}{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}s{Colors.ENDC}"
                        + f"| healthcheck_time_left={Colors.ORANGE}{format_duration(time_left)}{Colors.ENDC}..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = service.tasks(filters=filters)
                    time_left = healthcheck_timeout - (time.monotonic() - start_time)

                successful = len(task_list) == 0
                if successful:
                    await provision_log(
                        target_node,
                        f"  ✅ Service {Colors.BLUE}{service.name}{Colors.ENDC} removed",
                    )
                else:
                    await provision_log(
                        target_node,
                        f"  ⚠️ {Colors.ORANGE}Service {Colors.BLUE}{service.name}{Colors.ORANGE} still running{Colors.ENDC}",
                    )
                return successful
            except docker.errors.NotFound:
                # The node probably was removed from the cluster already
                return True

        services_drained = all(
            await asyncio.gather(
                *[wait_for_swarm_service_to_be_drained(service) for service in services]
            )
        )

        if services_drained:
            await provision_log(
                target_node,
                f"✅ ZaneOps services are removed from swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ENDC}",
            )
        else:
            await provision_log(
                target_node,
                f"⚠️ {Colors.ORANGE}ZaneOps services are still running on swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ORANGE} "
                f"after {Colors.GREY}{format_duration(healthcheck_timeout)}{Colors.ENDC}{Colors.ORANGE}, continuing anyway. "
                f"They will be stopped when the node leaves the swarm.{Colors.ENDC}",
            )

        return services_drained

    @activity.defn
    async def detach_swarm_node_from_cluster(self, ctx: SwarmNodeSSHContext):
        node = ctx.node
        await provision_log(
            node,
            [
                "",
                f"➡️ Making server {Colors.BLUE}{node.private_ip}{Colors.ENDC} leave the swarm...",
            ],
        )

        async def message_handler(message: str):
            await provision_log(node, f"{Colors.GREY}{message}{Colors.ENDC}")
            # The node already left the swarm, nothing to do
            return "not part of a swarm" in message or None

        exit_code, already_detached = await exec_cmd_in_server(
            ctx,
            cmd=f"docker swarm leave --force",
            output_handler=message_handler,
        )
        if exit_code == 0 or already_detached:
            await provision_log(
                node,
                f"✅ Server {Colors.BLUE}{node.private_ip}{Colors.ENDC} left the swarm",
            )
            return

        message = f"❌ {Colors.RED}Failed to make server {Colors.BLUE}{node.private_ip}{Colors.RED} leave the swarm{Colors.ENDC}"
        await provision_log(node, message, error=True)
        raise ApplicationError(message=message, non_retryable=True)

    @activity.defn
    async def remove_swarm_node_from_cluster(
        self, payload: DeprovisionSwarmNodePayload
    ):
        node = payload.target_node
        await provision_log(
            node,
            [
                "",
                f"➡️ Removing swarm node {Colors.BLUE}{node.swarm_node_id}{Colors.ENDC} from the cluster...",
            ],
        )
        try:
            swarm_node: DockerSwarmNode = self.docker_client.nodes.get(
                node.swarm_node_id
            )
            swarm_node.remove(force=True)
        except docker.errors.NotFound:
            await provision_log(
                node,
                f"⏩ Swarm node {Colors.BLUE}{node.swarm_node_id}{Colors.ENDC} is already removed from the cluster",
            )
        except docker.errors.APIError as e:
            message = f"❌ {Colors.RED}Failed to remove swarm node {Colors.BLUE}{node.swarm_node_id}{Colors.RED} from the cluster: {e}{Colors.ENDC}"
            await provision_log(node, message, error=True)
            raise ApplicationError(message=message, non_retryable=True)
        else:
            await provision_log(
                node,
                f"✅ Swarm node {Colors.BLUE}{node.swarm_node_id}{Colors.ENDC} removed from the cluster",
            )

    @activity.defn
    async def run_swarm_healthcheck(self) -> SwarmHealthcheckResult:
        all_nodes: list[DockerSwarmNode] = self.docker_client.nodes.list()

        nodes_statuses: dict[str, SwarmNodeHealthcheckResult] = {}
        for node in all_nodes:
            if node.id is not None:
                node = cast(DockerSwarmNode, node)
                nodes_statuses[cast(str, node.id)] = SwarmNodeHealthcheckResult(
                    status=node.attrs["Status"]["State"],
                    message=node.attrs["Status"].get("Message"),
                    availability=node.attrs["Spec"]["Availability"],
                    hostname=node.attrs["Description"]["Hostname"],
                )

        services: list[Service] = self.docker_client.services.list(
            filters={
                "label": ["com.docker.stack.namespace=zane"],
                "mode": "global",  # Only global services have tasks on every node
            },
        )

        for service in services:
            tasks = [
                DockerSwarmTask.from_dict(task)
                for task in service.tasks(filters={"desired-state": "running"})
            ]

            # A node can have more than one task for the same service (ex: during a `start-first` update),
            # we only keep the most recent one per node
            latest_task_per_node: dict[str, DockerSwarmTask] = {}
            for task in tasks:
                current = latest_task_per_node.get(task.NodeID)
                if current is None or task.Version.Index > current.Version.Index:
                    latest_task_per_node[task.NodeID] = task

            for node_id, task in latest_task_per_node.items():
                node_status = nodes_statuses.get(node_id)
                if node_status is None:
                    continue
                node_status.services[service.name] = SwarmNodeServiceHealthcheck(
                    service_name=service.name,
                    status=task.Status.State.value,
                    message=task.Status.Message,
                )

        return SwarmHealthcheckResult(nodes=nodes_statuses)

    @activity.defn
    async def save_swarm_healthcheck(self, result: SwarmHealthcheckResult):
        all_nodes = SwarmNode.objects.filter(
            Q(swarm_node_id__isnull=False)
            & ~Q(
                status__in=[
                    SwarmNode.Status.CREATED,
                    SwarmNode.Status.FAILED,
                    SwarmNode.Status.REMOVED,
                ]
            )
        ).all()

        async for node in all_nodes:
            node_status = result.nodes.get(cast(str, node.swarm_node_id))

            if node_status is not None:
                node.status_message = node_status.message
                node.hostname = node_status.hostname

                print(f"{node_status=}")
                if node_status.status != "ready":
                    node.status = SwarmNode.Status.DOWN
                else:
                    match node_status.availability:
                        case "active":
                            all_healthy = all(
                                [
                                    svc.status == DockerSwarmTaskState.RUNNING.value
                                    for svc in node_status.services.values()
                                ]
                            )
                            node.status = (
                                SwarmNode.Status.ACTIVE
                                if all_healthy
                                else SwarmNode.Status.UNHEALTHY
                            )
                        case "drain":
                            node.status = SwarmNode.Status.DRAINED
                        case "pause":
                            node.status = SwarmNode.Status.PAUSED

                    node.services = {  # type: ignore
                        svc.service_name: {
                            "message": svc.message,
                            "status": svc.status,
                        }
                        for svc in node_status.services.values()
                    }
                print(f"{node.services=}")
                print(f"{node.status=}")

        await asyncio.gather(
            *[
                node.asave(
                    update_fields=[
                        "status",
                        "hostname",
                        "services",
                        "status_message",
                        "updated_at",
                        "last_status_update",
                    ]
                )
                async for node in all_nodes
            ]
        )
