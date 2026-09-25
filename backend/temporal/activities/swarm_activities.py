import json
import os
import shlex
import shutil
from typing import Literal, cast

from temporalio import activity, workflow
import asyncio
import tempfile
import semver

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import Colors
    from temporal.helpers import empty_folder, exec_cmd_in_server
    from temporal.constants import (
        DOCKER_CHECK_SCRIPT,
        DOCKER_INSTALL_SCRIPT,
        DOCKER_ENABLE_SCRIPT,
        MINIMAL_DOCKER_VERSION_REQUIREMENTS,
    )


from ..shared import (
    DockerInstallContext,
    DockerSystemInfo,
    ProvisionSwarmNodePayload,
    ProvisionSwarmNodeContext,
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
    async def create_ssh_keys_temp_dir(self, details: ProvisionSwarmNodePayload):
        print("Creating temporary folder for SSH key..")
        temp_dir = tempfile.mkdtemp()
        print(f"Temporary folder created at {Colors.YELLOW}{temp_dir}{Colors.ENDC} ✅")

        print("Emptying temporary folder...")
        await asyncio.to_thread(empty_folder, temp_dir)
        print("Temporary emptyed ✅")

        main_node_key_location = os.path.join(temp_dir, f"{details.main_node.id}.key")
        new_node_key_location = os.path.join(temp_dir, f"{details.new_node.id}.key")

        print(f"Writing SSH Keys into  {Colors.YELLOW}{temp_dir}{Colors.ENDC}...")
        with open(
            main_node_key_location,
            "w",
        ) as file:
            file.write(details.main_node.ssh_key)
            print(
                f"Wrote ssh key for {Colors.BLUE}MAIN NODE{Colors.ENDC} at {Colors.YELLOW}{main_node_key_location}{Colors.ENDC} ✅"
            )
        print(
            f"Adjusting ssh key permissions for {Colors.YELLOW}{main_node_key_location}{Colors.ENDC}"
        )
        os.chmod(main_node_key_location, 0o600)
        print(f"Done ✅")

        with open(new_node_key_location, "+w") as file:
            file.write(details.new_node.ssh_key)
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
    async def enable_docker_service(self, ctx: ProvisionSwarmNodeContext):
        print(f"Enabling Docker system service...")
        exit_code, _ = await exec_cmd_in_server(
            ctx,
            cmd=DOCKER_ENABLE_SCRIPT,
        )
        if exit_code == 0:
            print(f"Succesfully Enabled Docker ✅ ")
        return exit_code == 0

    @activity.defn
    async def delete_ssh_keys_temp_dir(self, tmp_dir: str):
        print(
            f"Deleting temporary folder for SSH keys {Colors.YELLOW}{tmp_dir}{Colors.ENDC}..."
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("Temporary folder for SSH keys deleted ✅")
