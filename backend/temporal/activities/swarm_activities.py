import os
import shlex
import shutil
from typing import Literal

from temporalio import activity, workflow
import asyncio
import tempfile

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import Colors, multiline_command


from ..shared import (
    ProvisionSwarmNodePayload,
    ProvisionSwarmNodeContext,
    SwarmNodeDetails,
)


async def exec_cmd_in_server(ssh_key_dir: str, node: SwarmNodeDetails, *cmd: str):
    full_cmd = [
        "ssh",
        "-q",  # quiet mode
        "-p",
        str(node.ssh_port),
        "-i",
        node.get_ssh_key_path(ssh_key_dir),
        "-o",
        # Do not prompt for known_hosts
        "StrictHostKeyChecking=no",
        "-o",
        # Do not stpre pubkey known_hosts
        "UserKnownHostsFile=/dev/null",
        "-o",
        # Fail without asking for more input, no password prompt or anything
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        f"root@{node.private_ip}",
        *cmd,
    ]

    print(f"Running shell command : {Colors.YELLOW}{shlex.join(full_cmd)}{Colors.ENDC}")

    process = await asyncio.create_subprocess_exec(*full_cmd)
    await process.communicate()

    return process


"""
Provisionning steps:
1- check ssh connection
2- Check docker installation:
    a- if docker does not exist: => install docker and required packages 
    b- if docker exists && version >= 27.0.3 => ok
    c- if docker exists && version < 27.0.3 => reinstall docker (or upgrade docker)
3- Join swarm cluster with initial server IP (with the role chosen)
4- 
"""


class SwarmNodeActivities:
    @activity.defn
    async def create_ssh_key_temp_files(self, details: ProvisionSwarmNodePayload):
        temp_dir = tempfile.mkdtemp()
        main_node_key_location = os.path.join(temp_dir, f"{details.main_node.id}.key")
        new_node_key_location = os.path.join(temp_dir, f"{details.new_node.id}.key")

        with open(main_node_key_location, "+w") as file:
            file.write(details.main_node.ssh_key)

        with open(new_node_key_location, "+w") as file:
            file.write(details.new_node.ssh_key)

        return ProvisionSwarmNodeContext(temp_dir=temp_dir, details=details)

    @activity.defn
    async def test_ssh_connection(self, ctx: ProvisionSwarmNodeContext) -> str:
        node = ctx.details.new_node
        process = await exec_cmd_in_server(ctx.temp_dir, node)

        if process.returncode == 0:
            result = f" ✅ Connection to server {node.private_ip} over port {node.ssh_port} is possible"
        else:
            result = f"❌ Connection to server {node.private_ip} over port {node.ssh_port} is NOT possible"
        print(result)
        return result

    # @activity.defn
    # async def check_docker_version(self, details: SwarmNodeSSHKeyDetails) -> str:
    #     node = details.node
    #     cmd = get_ssh_exec_cmd(details, "exit 0")

    #     process = await asyncio.create_subprocess_exec(*cmd)
    #     await process.communicate()

    #     print(f"Running shell command : {Colors.YELLOW}{shlex.join(cmd)}{Colors.ENDC}")
    #     if process.returncode == 0:
    #         result = f" ✅ Connection to server {node.private_ip} over port {node.ssh_port} is possible"
    #     else:
    #         result = f"❌ Connection to server {node.private_ip} over port {node.ssh_port} is NOT possible"
    #     print(result)
    #     return result

    @activity.defn
    async def delete_ssh_key_temp_file(self, details: ProvisionSwarmNodeContext):
        try:
            shutil.rmtree(details.temp_dir, ignore_errors=True)
        except FileNotFoundError:
            # Probably already deleted
            print(f"Key file directory not found: {details.temp_dir}")
