import json
import os
import shutil
from temporalio import activity, workflow
import asyncio
import tempfile
import semver
from temporalio.exceptions import ApplicationError
from datetime import timedelta
import time

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import Colors, format_duration
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


from ..shared import (
    DockerInstallContext,
    DockerNodeUpdateContext,
    DockerSwarmJoinContext,
    DockerSwarmJoinCredentials,
    DockerSystemInfo,
    ProvisionSwarmNodePayload,
    ProvisionSwarmNodeContext,
    ProvisionSwarmNodeContextWithRole,
    DockerSwarmInfo,
    SwarmNodeDetails,
    SwarmNodeStatusResult,
)


"""
Provisionning steps:
1- check ssh connection
2- Check docker installation:
    a- if docker does not exist: => install docker and required packages 
    b- if docker exists && version >= 27.0.3 => ok
    c- if docker exists && version < 27.0.3 => reinstall docker (or upgrade docker)
3- Check if node part of already swarm and if the swarm role correspond to the one we chose
    a- if everything ok => skip
    b- if already part of a different swarm 
        or already part of a current swarm with different role 
        or not part of a swarm
        => quit swarm  (if member of swarm)
        => Then Join swarm cluster with initial server IP (with the role chosen) and private IP as advertise-addr
4- Update swarm node labels
5- Ok ?
"""


class SwarmNodeActivities:
    @activity.defn
    async def prepare_node_deployment(self, node: SwarmNodeDetails):
        await SwarmNode.objects.filter(id=node.id).aupdate(
            status=SwarmNode.Status.PROVISIONING
        )

    @activity.defn
    async def finish_and_save_node_deployment(self, result: SwarmNodeStatusResult):
        try:
            node = await SwarmNode.objects.filter(id=result.node.id).aget()

            node.status = result.status
            if result.docker_info:
                node.cpus = result.docker_info.NCPU
                node.memory_bytes = result.docker_info.MemTotal
                node.docker_version = result.docker_info.ServerVersion
            if result.swarm_hostname:
                node.hostname = result.swarm_hostname

            await node.asave(
                update_fields=[
                    "updated_at",
                    "status",
                    "cpus",
                    "memory_bytes",
                    "docker_version",
                    "hostname",
                ]
            )

        except SwarmNode.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent node.",
                non_retryable=True,
            )

    @activity.defn
    async def create_ssh_keys_temp_dir(self, payload: ProvisionSwarmNodePayload):
        print("Creating temporary folder for SSH key...")
        temp_dir = tempfile.mkdtemp()
        print(f"Temporary folder created at {Colors.YELLOW}{temp_dir}{Colors.ENDC} ✅")

        print("Emptying temporary folder...")
        await asyncio.to_thread(empty_folder, temp_dir)
        print("Temporary emptyed ✅")

        main_node_key_location = os.path.join(temp_dir, f"{payload.main_node.id}.key")
        new_node_key_location = os.path.join(temp_dir, f"{payload.new_node.id}.key")

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
            file.write(payload.new_node.ssh_key)
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
    async def test_ssh_connection(self, ctx: ProvisionSwarmNodeContext) -> bool:
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
        self, ctx: ProvisionSwarmNodeContext
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
        self, ctx: ProvisionSwarmNodeContextWithRole
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
        docker_client = docker.from_env()

        info = ctx.swarm_info
        node = ctx.node
        print(
            f"Updating labels for swarm node {Colors.BLUE}{info.NodeID}{Colors.ENDC}..."
        )
        try:
            swarm_node = docker_client.nodes.get(info.NodeID)

            labels = {}
            if "APP_SERVER" in node.cluster_roles:
                labels[settings.APP_SERVER_LABEL] = "true"
            if "BUILD_SERVER" in node.cluster_roles:
                labels[settings.BUILD_SERVER_LABEL] = "true"

            swarm_node.update(
                {
                    "Availability": "active",
                    "Role": ctx.node.swarm_role.lower(),
                    "Labels": labels,
                }
            )
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
        docker_client = docker.from_env()

        proxy_service: list[Service] = docker_client.services.list(
            filters={"label": ["zane.role=proxy"]},
            status=True,
        )

        log_collector_service: list[Service] = docker_client.services.list(
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
                    f"service `{Colors.BLUE}{service.name}{Colors.ENDC}` is not updated , "
                    + f"| retrying in `{Colors.ORANGE}{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}s{Colors.ENDC}`"
                    + f"| healthcheck_time_left={Colors.ORANGE}{format_duration(time_left)}{Colors.ENDC}..."
                )
                await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                task_list = task_list = service.tasks(filters=filters)
                print(f"{task_list=}")
                time_left = healthcheck_timeout - (time.monotonic() - start_time)

            return len(task_list) > 0

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
