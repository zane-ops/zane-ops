import os
import shlex

from temporalio import activity, workflow
import asyncio
import tempfile

with workflow.unsafe.imports_passed_through():
    from zane_api.utils import Colors, multiline_command


from ..shared import SwarmNodeDetails, SwarmNodeSSHKeyDetails


class SwarmNodeActivities:
    @activity.defn
    async def create_ssh_key_temp_file(self, node: SwarmNodeDetails):
        private_fd, key_path = tempfile.mkstemp()
        with os.fdopen(private_fd, "wb") as tmp:
            tmp.write(node.ssh_key.encode())
        return SwarmNodeSSHKeyDetails(path=key_path, node=node)

    @activity.defn
    async def test_ssh_connection(self, details: SwarmNodeSSHKeyDetails) -> str:
        node = details.node
        cmd = [
            "ssh",
            "-q",  # quiet mode
            "-p",
            str(node.ssh_port),
            "-i",
            details.path,
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
            "exit 0",
        ]

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.communicate()

        cmd_string = multiline_command(shlex.join(cmd))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        print(log_message)
        if process.returncode == 0:
            result = f" ✅ Connection to server {node.private_ip} over port {node.ssh_port} is possible"
        else:
            result = f"❌ Connection to server {node.private_ip} over port {node.ssh_port} is NOT possible"
        print(result)
        return result

    @activity.defn
    async def delete_ssh_key_temp_file(self, details: SwarmNodeSSHKeyDetails):
        try:
            os.remove(details.path)
        except FileNotFoundError:
            # Probably already deleted
            print(f"Key file not found: {details.path}")
