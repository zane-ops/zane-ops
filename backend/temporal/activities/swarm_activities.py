import json
import os
import shlex
import shutil
from typing import Literal, cast

from temporalio import activity, workflow
import asyncio
import tempfile

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import Colors, multiline_command
    from temporal.helpers import empty_folder
    from zane_api.process import (
        AyncSubProcessRunner,
        OutputHandlerFunction,
        default_output_handler,
    )


from ..shared import (
    DockerInstallContext,
    DockerSystemInfo,
    ProvisionSwarmNodePayload,
    ProvisionSwarmNodeContext,
    SwarmNodeDetails,
)


async def exec_cmd_in_server[T](
    ssh_key_dir: str,
    node: SwarmNodeDetails,
    cmd: str,
    output_handler: OutputHandlerFunction[T] = default_output_handler,
) -> tuple[int | None, T | None]:
    heartbeat_task = None
    cancel_event = asyncio.Event()
    exit_code: int | None = None
    result: T | None = None

    try:

        async def send_heartbeat():
            """
            We want this activity to be cancellable,
            for activities to be cancellable, they need to send regular heartbeats:
            https://docs.temporal.io/develop/python/cancellation#cancel-activity
            """
            while True:
                activity.heartbeat(
                    "Heartbeat from `clone_repository_and_checkout_to_commit()`..."
                )
                await asyncio.sleep(0.1)

        heartbeat_task = asyncio.create_task(send_heartbeat())

        full_cmd = [
            "ssh",
            "-p",
            str(node.ssh_port),
            "-i",
            node.get_ssh_key_path(ssh_key_dir),
            # Do not prompt for known_hosts
            "-o",
            "StrictHostKeyChecking=no",
            # Do not store pubkey known_hosts
            "-o",
            "UserKnownHostsFile=/dev/null",
            # Fail without asking for more input, no password prompt or anything
            "-o",
            "BatchMode=yes",
            # SSH connection timeout of 5sec
            "-o",
            "ConnectTimeout=5",
            f"root@{node.private_ip}",
            cmd,
        ]

        print(
            f"Running shell command : {Colors.YELLOW}{shlex.join(full_cmd)}{Colors.ENDC}"
        )

        runner = AyncSubProcessRunner(
            command=shlex.join(full_cmd),
            cancel_event=cancel_event,
            operation_name="ssh",
            output_handler=output_handler,
        )
        cmd_task = asyncio.create_task(runner.run())

        done_first, _ = await asyncio.wait(
            [heartbeat_task, cmd_task], return_when=asyncio.FIRST_COMPLETED
        )

        if cmd_task in done_first:
            exit_code, raw_result = cmd_task.result()
            result = cast(T | None, raw_result)
            print("`cmd_task()` finished first")
        else:
            print("cancelling `cmd_task()`")
            cmd_task.cancel()
            await cmd_task
    except asyncio.CancelledError:
        cancel_event.set()
        raise
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
    return exit_code, result


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
            f"Updating ssh key permissions for {Colors.YELLOW}{main_node_key_location}{Colors.ENDC} to 600"
        )
        os.chmod(main_node_key_location, 0o600)
        print(f"Done ✅")

        with open(new_node_key_location, "+w") as file:
            file.write(details.new_node.ssh_key)
            print(
                f"Wrote ssh key for the {Colors.BLUE}NEW NODE{Colors.ENDC} at {Colors.YELLOW}{new_node_key_location}{Colors.ENDC} ✅"
            )
        print(
            f"Updating ssh key permissions for {Colors.YELLOW}{new_node_key_location}{Colors.ENDC} to 600"
        )
        os.chmod(new_node_key_location, 0o600)
        print(f"Done ✅")

        return ProvisionSwarmNodeContext(temp_dir=temp_dir, details=details)

    @activity.defn
    async def test_ssh_connection(self, ctx: ProvisionSwarmNodeContext) -> bool:
        node = ctx.details.new_node
        print(
            f"Testing SSH Connection to server {Colors.YELLOW}{node.private_ip}{Colors.ENDC} over port {Colors.YELLOW}{node.ssh_port}{Colors.ENDC}..."
        )
        exit_code, _ = await exec_cmd_in_server(ctx.temp_dir, node, cmd="exit 0")

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
        node = ctx.details.new_node

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

        check_docker_version = (
            "command -v docker >/dev/null 2>&1 && docker info -f json"
        )

        print(f"Checking existing Docker installation...")
        exit_code, result = await exec_cmd_in_server(
            ctx.temp_dir, node, cmd=check_docker_version, output_handler=message_handler
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
        if ctx.info is not None:
            print("Docker installed on this server")
        else:
            pass  # install

    @activity.defn
    async def delete_ssh_keys_temp_dir(self, ctx: ProvisionSwarmNodeContext):
        print(
            f"Deleting temporary folder for SSH keys {Colors.YELLOW}{ctx.temp_dir}{Colors.ENDC}..."
        )
        shutil.rmtree(ctx.temp_dir, ignore_errors=True)
        print("Temporary folder for SSH keys deleted ✅")
