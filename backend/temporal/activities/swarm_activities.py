from copy import deepcopy
import json
import os
import shutil
from typing import cast
from temporalio import activity, workflow
import asyncio
import tempfile
import semver
from temporalio.exceptions import ApplicationError
from datetime import timedelta
import time

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import Colors, format_duration, DockerSwarmTask
    from temporal.helpers import empty_folder, exec_cmd_in_server
    from temporal.constants import (
        DOCKER_CHECK_SCRIPT,
        DOCKER_INSTALL_SCRIPT,
        MINIMAL_DOCKER_VERSION_REQUIREMENTS,
        DOCKER_SYSTEM_INFO_CMD,
    )
    import docker
    import docker.errors
    from docker.models.services import Service
    from django.conf import settings
    from swarm.models import SwarmNode
    from docker.models.nodes import Node as DockerSwarmNode
    from django.utils import timezone
    from django.db.models import Q


from ..shared import (
    SwarmHealthcheckResult,
    SwarmNodeHealthcheckResult,
    SwarmNodePair,
    ClusterSwarmNodePair,
    DockerInstallContext,
    DockerNodeUpdateContext,
    DockerSwarmJoinContext,
    DockerSwarmJoinCredentials,
    DockerSystemInfo,
    RemoveSwarmNodeContext,
    SwarmNodeSSHContext,
    GetSwarmJoinTokenInput,
    DockerSwarmInfo,
    SwarmNodeDetails,
    SwarmNodeServiceHealthcheck,
    SwarmNodeStatusResult,
)


class SwarmNodeActivities:
    def __init__(self):
        self.docker_client = docker.from_env()

    @activity.defn
    async def prepare_node_deployment(self, node: SwarmNodeDetails):
        await SwarmNode.objects.filter(id=node.id).aupdate(
            status=SwarmNode.Status.PROVISIONING,
            last_status_update=timezone.now(),
        )

    @activity.defn
    async def finish_and_save_node_deployment(self, result: SwarmNodeStatusResult):
        try:
            node = await SwarmNode.objects.filter(id=result.id).aget()

            node.status = result.status
            if result.docker_info:
                node.cpus = result.docker_info.NCPU
                node.memory_bytes = result.docker_info.MemTotal
                node.docker_version = result.docker_info.ServerVersion
            if result.swarm_hostname:
                node.hostname = result.swarm_hostname
            if result.docker_info is not None and result.docker_info.Swarm is not None:
                node.swarm_node_id = result.docker_info.Swarm.NodeID

            await node.asave(
                update_fields=[
                    "updated_at",
                    "status",
                    "cpus",
                    "memory_bytes",
                    "docker_version",
                    "hostname",
                    "swarm_node_id",
                    "last_status_update",
                ]
            )

        except SwarmNode.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent node.",
                non_retryable=True,
            )

    @activity.defn
    async def clear_removed_swarm_node_attributes(self, result: SwarmNodeStatusResult):
        print(
            f"Clearing swarm attributes for removed node {Colors.BLUE}{result.id}{Colors.ENDC}..."
        )
        updated = await SwarmNode.objects.filter(id=result.id).aupdate(
            status=result.status,
            swarm_node_id=None,
            hostname=None,
            docker_version=None,
            cpus=None,
            memory_bytes=None,
            last_status_update=timezone.now(),
        )
        if updated == 0:
            raise ApplicationError(
                "Cannot clear attributes of a non existent node.",
                non_retryable=True,
            )
        print(
            f"Swarm attributes cleared for removed node {Colors.BLUE}{result.id}{Colors.ENDC} ✅"
        )

    @activity.defn
    async def create_ssh_keys_temp_dir(self, payload: SwarmNodePair):
        print("Creating temporary folder for SSH key...")
        temp_dir = tempfile.mkdtemp()
        print(f"Temporary folder created at {Colors.YELLOW}{temp_dir}{Colors.ENDC} ✅")

        print("Emptying temporary folder...")
        await asyncio.to_thread(empty_folder, temp_dir)
        print("Temporary emptyed ✅")

        main_node_key_location = os.path.join(temp_dir, f"{payload.main_node.id}.key")
        new_node_key_location = os.path.join(temp_dir, f"{payload.target_node.id}.key")

        print(f"Writing SSH Keys into  {Colors.YELLOW}{temp_dir}{Colors.ENDC}...")
        with open(
            main_node_key_location,
            "w",
        ) as file:
            file.write(payload.main_node.ssh_key)
            print(
                f"Wrote ssh key for {Colors.BLUE}MAIN NODE{Colors.ENDC} at {Colors.YELLOW}{main_node_key_location}{Colors.ENDC} ✅"
            )
        print(
            f"Adjusting ssh key permissions for {Colors.YELLOW}{main_node_key_location}{Colors.ENDC}"
        )
        os.chmod(main_node_key_location, 0o600)
        print(f"Done ✅")

        with open(new_node_key_location, "+w") as file:
            file.write(payload.target_node.ssh_key)
            print(
                f"Wrote ssh key for the {Colors.BLUE}NEW NODE{Colors.ENDC} at {Colors.YELLOW}{new_node_key_location}{Colors.ENDC} ✅"
            )
        print(
            f"Adjusting ssh key permissions for {Colors.YELLOW}{new_node_key_location}{Colors.ENDC}"
        )
        os.chmod(new_node_key_location, 0o600)
        print(f"Done ✅")

        return temp_dir

    @activity.defn
    async def test_ssh_connection(self, ctx: SwarmNodeSSHContext) -> bool:
        node = ctx.node
        print(
            f"Testing SSH Connection to server {Colors.YELLOW}{node.private_ip}{Colors.ENDC} over port {Colors.YELLOW}{node.ssh_port}{Colors.ENDC}..."
        )
        exit_code, _ = await exec_cmd_in_server(ctx, cmd="exit 0")

        can_connect = exit_code == 0
        print(f"{exit_code=}")

        if can_connect:
            print(
                f"✅ Connection to server {node.private_ip} over port {node.ssh_port} is possible"
            )
        else:
            print(
                f"❌ Connection to server {node.private_ip} over port {node.ssh_port} is NOT possible"
            )
        return can_connect

    @activity.defn
    async def check_docker_installation(
        self, ctx: SwarmNodeSSHContext
    ) -> DockerSystemInfo | None:
        async def message_handler(message: str):
            print(message)
            system_info: DockerSystemInfo | None = None
            try:
                parsed_data = json.loads(message)
            except json.JSONDecodeError:
                # Invalid JSON, not the data we are looking for
                pass
            else:
                system_info = DockerSystemInfo.from_dict(parsed_data)
            return system_info

        check_docker_version = DOCKER_CHECK_SCRIPT

        print(f"Checking existing Docker installation...")
        exit_code, result = await exec_cmd_in_server(
            ctx, cmd=check_docker_version, output_handler=message_handler
        )
        if exit_code == 0 and result is not None:
            print(
                f"Found Docker installation with version {Colors.YELLOW}{result.ServerVersion}{Colors.ENDC} ✅ "
            )
            return result
        else:
            print(f"Docker is not installed on this server ❌")

        return None

    @activity.defn
    async def install_latest_docker_version(
        self, ctx: DockerInstallContext
    ) -> DockerSystemInfo | None:
        print(
            f"Installing docker on server {Colors.BLUE}{ctx.node.private_ip}{Colors.ENDC}..."
        )
        if (
            ctx.info is not None
            # Check that docker version meets minimal version requirements
            and semver.compare(
                ctx.info.ServerVersion, MINIMAL_DOCKER_VERSION_REQUIREMENTS
            )
            >= 0
        ):
            print(
                f"{Colors.YELLOW}Docker v{ctx.info.ServerVersion}{Colors.ENDC} already installed on server, skipping installation ⏩"
            )
            return ctx.info

        async def message_handler(message: str):
            print(message)
            system_info: DockerSystemInfo | None = None
            try:
                parsed_data = json.loads(message)
            except json.JSONDecodeError:
                # Invalid JSON, not the data we are looking for
                pass
            else:
                system_info = DockerSystemInfo.from_dict(parsed_data)
            return system_info

        exit_code, result = await exec_cmd_in_server(
            ctx,
            cmd=DOCKER_INSTALL_SCRIPT,
            output_handler=message_handler,
        )

        if exit_code == 0 and result is not None:
            print(
                f"Succesfully Installed Docker {Colors.YELLOW}v{result.ServerVersion}{Colors.ENDC} ✅ "
            )
            return result
        else:
            print(
                f"{Colors.RED}Failed to install docker on server {Colors.BLUE}{ctx.node.private_ip} ❌{Colors.ENDC}"
            )
        return result

    @activity.defn
    async def get_swarm_join_token(
        self, ctx: GetSwarmJoinTokenInput
    ) -> DockerSwarmJoinCredentials | None:
        async def message_handler(message: str):
            print(message)

            if message.strip().startswith("docker swarm join --token"):
                token, manager_ip = message.replace(
                    "docker swarm join --token", ""
                ).split()

                return token, manager_ip

        print(f"Get Docker swarm Join credentials...")
        exit_code, result = await exec_cmd_in_server(
            ctx,
            cmd=f"docker swarm join-token {ctx.swarm_role.lower()}",
            output_handler=message_handler,
        )
        if exit_code == 0 and result is not None:
            credentials = DockerSwarmJoinCredentials(
                token=result[0],
                manager_addr=result[1],
            )
            print(
                f"Got credentials {credentials.token=} {credentials.manager_addr=} ✅"
            )
            return credentials
        print(f"{Colors.RED}Failed to get Swarm Join credentials ❌{Colors.ENDC}")
        return None

    @activity.defn
    async def join_swarm_cluster(
        self, ctx: DockerSwarmJoinContext
    ) -> DockerSwarmInfo | None:
        info = ctx.info
        node = ctx.node
        credentials = ctx.credentials
        print(
            f"Joining server {Colors.BLUE}{node.private_ip}{Colors.ENDC} to docker swarm cluster from manager {Colors.BLUE}{credentials.manager_addr}{Colors.ENDC}..."
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
                print(
                    f"Server is already part of the swarm cluster with the {Colors.YELLOW}{node.swarm_role}{Colors.ENDC} with ID {Colors.YELLOW}{info.Swarm.NodeID}{Colors.ENDC}, skipping join ⏩"
                )
                return info.Swarm

        async def message_handler(message: str):
            print(message)
            system_info: DockerSystemInfo | None = None
            try:
                parsed_data = json.loads(message)
            except json.JSONDecodeError:
                # Invalid JSON, not the data we are looking for
                pass
            else:
                system_info = DockerSystemInfo.from_dict(parsed_data)
            return system_info

        exit_code, result = await exec_cmd_in_server(
            ctx,
            cmd=f"docker swarm leave --force >/dev/null 2>&1; docker swarm join --advertise-addr {node.private_ip} --token {credentials.token} {credentials.manager_addr} && {DOCKER_SYSTEM_INFO_CMD}",
            output_handler=message_handler,
        )
        if exit_code == 0 and result is not None and result.Swarm is not None:
            print(
                f"Server {Colors.BLUE}{node.private_ip}{Colors.ENDC} joined the cluster as a {Colors.BLUE}{node.swarm_role.lower()}{Colors.ENDC} with ID {Colors.YELLOW}{result.Swarm.NodeID}{Colors.ENDC} ✅"
            )
            return result.Swarm
        else:
            print(
                f"{Colors.RED}Failed to add server {Colors.BLUE}{node.private_ip}{Colors.ENDC} swarm cluster ❌{Colors.ENDC}"
            )

        return None

    @activity.defn
    async def update_node_labels(self, ctx: DockerNodeUpdateContext):

        info = ctx.swarm_info
        node = ctx.node
        print(
            f"Updating labels for swarm node {Colors.BLUE}{info.NodeID}{Colors.ENDC}..."
        )
        try:
            swarm_node: DockerSwarmNode = self.docker_client.nodes.get(info.NodeID)
            original_spec = swarm_node.attrs["Spec"]

            new_spec = deepcopy(original_spec)

            labels = new_spec.get("Labels", {})
            if "APP_SERVER" in node.cluster_roles:
                labels[settings.APP_SERVER_LABEL] = "true"
            if "BUILD_SERVER" in node.cluster_roles:
                labels[settings.BUILD_SERVER_LABEL] = "true"

            new_spec["role"] = node.swarm_role.lower()
            new_spec["Labels"] = labels
            swarm_node.update(new_spec)
        except docker.errors.APIError:
            print(
                f"{Colors.RED}Failed to update swarm labels {info.NodeID} ❌{Colors.ENDC}"
            )
            return None
        else:
            print(
                f"Succesfully updated labels for Swarm Node {Colors.BLUE}{info.NodeID}{Colors.ENDC} ✅"
            )

        return swarm_node.attrs["Description"]["Hostname"]

    @activity.defn
    async def wait_for_global_services_to_be_propagated(
        self, swarm_info: DockerSwarmInfo
    ):

        proxy_service: list[Service] = self.docker_client.services.list(
            filters={"label": ["zane.role=proxy"]},
            status=True,
        )

        log_collector_service: list[Service] = self.docker_client.services.list(
            filters={"label": ["zane.role=log-collector"]},
        )

        services = [*proxy_service, *log_collector_service]

        healthcheck_timeout = timedelta(minutes=3).total_seconds()

        async def wait_for_swarm_service_to_be_updated(service: Service):

            print(
                f"Waiting for service `{Colors.BLUE}{service.name=}{Colors.ENDC}` to be updated..."
            )
            start_time = time.monotonic()
            time_left = timedelta(minutes=3).total_seconds()

            filters = {"node": swarm_info.NodeID, "desired-state": "running"}
            task_list: list = service.tasks(filters=filters)

            print(f"{filters=}")

            while len(task_list) == 0 and time_left >= 1:
                print(
                    f"Swarm service {Colors.BLUE}{service.name}{Colors.ENDC} is not updated, "
                    + f"| retrying in {Colors.ORANGE}{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}s{Colors.ENDC}"
                    + f"| healthcheck_time_left={Colors.ORANGE}{format_duration(time_left)}{Colors.ENDC}..."
                )
                await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                task_list = task_list = service.tasks(filters=filters)
                print(f"{task_list=}")
                time_left = healthcheck_timeout - (time.monotonic() - start_time)

            successful = len(task_list) > 0
            if successful:
                print(
                    f"Succesfully updated swarm service {Colors.BLUE}{service.name}{Colors.ENDC} ✅"
                )
            return successful

        services_updated = await asyncio.gather(
            *[wait_for_swarm_service_to_be_updated(service) for service in services]
        )

        return all(services_updated)

    @activity.defn
    async def delete_ssh_keys_temp_dir(self, tmp_dir: str):
        print(
            f"Deleting temporary folder for SSH keys {Colors.YELLOW}{tmp_dir}{Colors.ENDC}..."
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("Temporary folder for SSH keys deleted ✅")

    @activity.defn
    async def drain_swarm_node_and_remove_labels(self, payload: ClusterSwarmNodePair):

        target_node = payload.target_node
        print(
            f"Draining swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ENDC}..."
        )
        try:
            swarm_node = self.docker_client.nodes.get(target_node.swarm_node_id)
            original_spec = swarm_node.attrs["Spec"]

            new_spec = deepcopy(original_spec)
            new_spec["Labels"] = {}
            new_spec["Availability"] = "drain"

            swarm_node.update(new_spec)
        except docker.errors.NotFound:
            print(
                f"{Colors.RED}Failed to drain swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.RED} and remove its labels ❌{Colors.ENDC}"
            )
            return False
        else:
            print(
                f"Swarm node {Colors.BLUE}{target_node.swarm_node_id}{Colors.ENDC} drained and labels removed, no new tasks will be scheduled on it ✅"
            )

        return True

    @activity.defn
    async def wait_for_global_services_to_be_drained(
        self, payload: ClusterSwarmNodePair
    ):

        target_node = payload.target_node

        proxy_service: list[Service] = self.docker_client.services.list(
            filters={"label": ["zane.role=proxy"]},
            status=True,
        )

        log_collector_service: list[Service] = self.docker_client.services.list(
            filters={"label": ["zane.role=log-collector"]},
        )

        services = [*proxy_service, *log_collector_service]

        healthcheck_timeout = timedelta(minutes=3).total_seconds()

        async def wait_for_swarm_service_to_be_updated(service: Service):
            try:
                print(
                    f"Waiting for service `{Colors.BLUE}{service.name=}{Colors.ENDC}` to be updated..."
                )
                start_time = time.monotonic()
                time_left = timedelta(minutes=3).total_seconds()

                filters = {
                    "node": target_node.swarm_node_id,
                    "desired-state": "running",
                }
                task_list: list = service.tasks(filters=filters)

                print(f"{filters=}")

                while len(task_list) > 0 and time_left >= 1:
                    print(
                        f"Swarm service {Colors.BLUE}{service.name}{Colors.ENDC} is not updated , "
                        + f"| retrying in {Colors.ORANGE}{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}s{Colors.ENDC}"
                        + f"| healthcheck_time_left={Colors.ORANGE}{format_duration(time_left)}{Colors.ENDC}..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = task_list = service.tasks(filters=filters)
                    print(f"{task_list=}")
                    time_left = healthcheck_timeout - (time.monotonic() - start_time)

                successful = len(task_list) == 0
                if successful:
                    print(
                        f"Succesfully updated swarm service {Colors.BLUE}{service.name}{Colors.ENDC} ✅"
                    )
                return successful
            except docker.errors.NotFound:
                # The node probably was removed from the cluster already
                return True

        services_updated = await asyncio.gather(
            *[wait_for_swarm_service_to_be_updated(service) for service in services]
        )

        return all(services_updated)

    @activity.defn
    async def detach_swarm_node_from_cluster(self, ctx: SwarmNodeSSHContext):
        node = ctx.node
        print(
            f"detaching swarm node {Colors.BLUE}{node.id}{Colors.ENDC} from cluster..."
        )
        exit_code, _ = await exec_cmd_in_server(
            ctx,
            cmd=f"docker swarm leave --force",
        )
        if exit_code == 0:
            print(
                f"Swarm node {Colors.BLUE}{node.id}{Colors.ENDC} succesfully detached from cluster ✅"
            )
            return True
        return False

    @activity.defn
    async def remove_swarm_node_from_cluster(self, ctx: RemoveSwarmNodeContext):
        node = ctx.target_node
        print(f"Removing node {Colors.BLUE}{node.id}{Colors.ENDC} from cluster...")
        exit_code, _ = await exec_cmd_in_server(
            ctx.activity_ctx,
            cmd=f"docker node rm {node.swarm_node_id} --force",
        )
        if exit_code == 0:
            print(
                f"Swarm node {Colors.BLUE}{node.id}{Colors.ENDC} succesfully removed from cluster ✅"
            )
            return True
        return False

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
                )

        proxy_service: list[Service] = self.docker_client.services.list(
            filters={"label": ["zane.role=proxy"]},
        )

        log_collector_service: list[Service] = self.docker_client.services.list(
            filters={"label": ["zane.role=log-collector"]},
        )

        if len(proxy_service) > 0:
            service = proxy_service[0]
            tasks = [
                DockerSwarmTask.from_dict(task)
                for task in service.tasks(filters={"desired-state": "running"})
            ]

            for task in tasks:
                nodes_statuses[task.NodeID].services["proxy"] = (
                    SwarmNodeServiceHealthcheck(
                        service_name=service.name,
                        status=task.Status.State.value,
                        message=task.Status.Message,
                    )
                )

        if len(log_collector_service) > 0:
            service = log_collector_service[0]
            tasks = [
                DockerSwarmTask.from_dict(task)
                for task in service.tasks(filters={"desired-state": "running"})
            ]

            for task in tasks:
                nodes_statuses[task.NodeID].services["log_collector"] = (
                    SwarmNodeServiceHealthcheck(
                        service_name=service.name,
                        status=task.Status.State.value,
                        message=task.Status.Message,
                    )
                )

        return SwarmHealthcheckResult(nodes=nodes_statuses)

    @activity.defn
    async def save_swarm_healthcheck(self, result: SwarmHealthcheckResult):
        all_nodes = SwarmNode.objects.filter(
            Q(swarm_node_id__isnull=False)
            & ~Q(status__in=["CREATED", "PROVISIONING", "FAILED", "REMOVED"])
        ).all()

        async for node in all_nodes:
            node_status = result.nodes.get(cast(str, node.swarm_node_id))

            if node_status is not None:
                node.status_message = node_status.message

                print(f"{node_status=}")
                if node_status.status != "ready":
                    node.status = SwarmNode.Status.DOWN
                else:
                    match node_status.availability:
                        case "active":
                            node.status = SwarmNode.Status.ACTIVE
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

        async def save_node(node: SwarmNode):
            await node.asave(
                update_fields=[
                    "status",
                    "services",
                    "status_message",
                    "updated_at",
                    "last_status_update",
                ]
            )

        await asyncio.gather(*[save_node(node) async for node in all_nodes])
