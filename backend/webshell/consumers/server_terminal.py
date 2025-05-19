import asyncio
import json
import os
import shlex
import signal
import traceback
from typing import Optional, cast

from channels.generic.websocket import AsyncWebsocketConsumer
import docker
from zane_api.utils import Colors
import pty
import fcntl
import termios
import struct

from ..serializers import (
    DeploymentTerminalResizeSerializer,
)
from rest_framework.utils.serializer_helpers import ReturnDict
from ..exceptions import log_consumer_exceptions
from ..models import SSHKey
from django.conf import settings
import tempfile


@log_consumer_exceptions
class ServerTerminalConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docker_client = docker.from_env()
        self.key_path: Optional[str] = None
        self.ssh_key: Optional[SSHKey] = None
        # file descriptor used for writing to the terminal
        self.master_file_descriptor: Optional[int] = None
        self.process: Optional[asyncio.subprocess.Process] = None

    async def connect(self):
        kwargs = self.scope["url_route"]["kwargs"]
        key_slug = kwargs["slug"]

        await self.accept()

        try:
            self.ssh_key = await SSHKey.objects.aget(slug=key_slug)
        except SSHKey.DoesNotExist:
            return await self.send(
                f"An SSHKey with the slug `{key_slug}` does not exist{Colors.ENDC}\n\r",
                close=True,
            )

        # gateway = network.attrs['IPAM']['Config'][0]['Gateway']
        if settings.ENVIRONMENT == settings.PRODUCTION_ENV:
            docker_bridge_network = self.docker_client.networks.get("bridge")
            gateway = docker_bridge_network.attrs["IPAM"]["Config"][0]["Gateway"]
        else:
            # we use `docker-compose` locally, so we can access the host using `host.docker.internal`
            gateway = "host.docker.internal"

        await self.send(
            f"Connecting to default network `{gateway}` using key `{self.ssh_key.slug}` \n\r"
        )

        print("Creating temp file for private key...")
        private_fd, self.key_path = tempfile.mkstemp()
        with os.fdopen(private_fd, "wb") as tmp:
            tmp.write(self.ssh_key.private_key.encode())

        print(f"SSH key file wrote succesfully to `{self.key_path}` ✅")

        # 1) Open a new local PTY
        master_fd, slave_fd = pty.openpty()

        # 2) Spawn `ssh -i <key-path> <user>@<gateway>` attached to that slave PTY
        cmd = [
            "ssh",
            "-t",
            "-i",
            self.key_path,
            # disable strict host key checking
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{self.ssh_key.user}@{gateway}",
            "TERM=xterm $SHELL",
        ]

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
        )
        os.close(slave_fd)  # we only need the master end
        self.master_file_descriptor = master_fd

        # 3) Hook the master FD into asyncio so we get output as it arrives
        loop = asyncio.get_running_loop()
        loop.add_reader(master_fd, self._on_pty_data)

        welcome_message = [
            f"{Colors.BLUE}Running {shlex.join(cmd)} {Colors.ENDC}\n\r",
            f"{Colors.GREY}----------------------------------------{Colors.ENDC}\n\r",
            f"{Colors.GREY}To allow login with this SSH key, please add this public key to your ssh folder using these commands:{Colors.ENDC}\n\r"
            f"{Colors.GREY}1- mkdir -p $HOME/.ssh{Colors.ENDC}\n\r"
            f"{Colors.GREY}2- touch $HOME/.ssh/authorized_keys{Colors.ENDC}\n\r"
            f"{Colors.GREY}3- chmod 600 $HOME/.ssh/authorized_keys{Colors.ENDC}\n\r"
            f"{Colors.GREY}4- Copy the public key and add it at the end the file in a new line at `$HOME/.ssh/authorized_keys`{Colors.ENDC}\n\r"
            f"{Colors.GREY}----------------------------------------{Colors.ENDC}\n\r",
        ]
        for message in welcome_message:
            await self.send(text_data=message)

        # 4) Start a watcher that closes the WebSocket when the shell exits
        self.exit_watcher = asyncio.create_task(self._watch_process())

    async def _watch_process(self):
        # Wait until the subprocess (the shell) exits
        if self.process is not None:
            return_code = await self.process.wait()
            # Inform the client
            await self.send(
                text_data=f"\n\r[Process exited with code {return_code}]\n\r"
            )
        # Close the WS
        await self.close()

    def _on_pty_data(self):
        if self.master_file_descriptor is None:
            return

        try:
            data = os.read(self.master_file_descriptor, 1024)
        except OSError:
            return
        except Exception as e:
            print(f"Error writing to the file descriptor: {e=}")
            traceback.print_exc()
            return
        if not data:
            return

        # send output back to the WebSocket
        asyncio.get_event_loop().create_task(
            self.send(text_data=data.decode(errors="ignore"))
        )

    async def disconnect(self, code):
        print("\nDisconnecting...")
        # stop reading from the PTY
        loop = asyncio.get_running_loop()
        if self.master_file_descriptor is not None:
            if self.process is not None and self.process.returncode is None:
                print(
                    f"[disconnect] Send exit to subprocess {self.master_file_descriptor=} {self.process=}..."
                )
                # Try to send `exit` to the underlying subprocess if not closed properly
                try:
                    os.write(self.master_file_descriptor, "exit\r".encode())
                except OSError:
                    pass
                else:
                    print(
                        f"[disconnect] Waiting for process to be done {self.process=}..."
                    )

                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=1.5)
                    finally:
                        if self.process.returncode is not None:
                            print("Process exited correctly")
                    if self.process.returncode is not None:
                        print("[disconnect] Process exited correctly")

            print(f"Closing file descriptor {self.master_file_descriptor=}...")
            loop.remove_reader(self.master_file_descriptor)
            os.close(self.master_file_descriptor)

            print("Done ✅")

        # terminate the subprocess cleanly
        if self.process is not None:
            if self.process.returncode is None:
                print(
                    f"[disconnect] Process not finished, killing process {self.process=} with {Colors.RED}SIGTEM{Colors.ENDC}..."
                )
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                await self.process.wait()
                print("Done ✅")
            print(f"[disconnect]: Process exited with code {self.process.returncode}")

        print("[disconnect] Deleting private ssh key file...")
        if self.key_path:
            try:
                os.remove(self.key_path)
            except FileNotFoundError:
                print(f"[disconnect] Key file not found: {self.key_path}")
        print("[disconnect] SSH private key file deleted succesfully ✅")

    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ):
        """Send user input from WebSocket to the container."""
        print(f"Received: {text_data=} {self.master_file_descriptor=}")

        if not text_data or not self.master_file_descriptor:
            return

        # check for resize messages
        try:
            print("check for resize messages...")
            serializer = DeploymentTerminalResizeSerializer(data=json.loads(text_data))
            if serializer.is_valid():
                data = cast(ReturnDict, serializer.data)
                if data.get("type") == "resize":
                    cols = data.get("cols")
                    rows = data.get("rows")
                    # perform ioctl on the PTY master
                    size = struct.pack("HHHH", rows, cols, 0, 0)
                    result = fcntl.ioctl(
                        self.master_file_descriptor, termios.TIOCSWINSZ, size
                    )

                    if self.process and self.process.pid:
                        try:
                            os.killpg(os.getpgid(self.process.pid), signal.SIGWINCH)
                            print(
                                f"Sent SIGWINCH to process group {os.getpgid(self.process.pid)}"
                            )
                        except ProcessLookupError:
                            print("Process already exited, cannot send SIGWINCH")

                    print(
                        f"Applied resize: rows={rows}, cols={cols} => {struct.unpack('HHHH', result)}"
                    )
                    return
            print("Received JSON message but not resize message!")
        except (json.JSONDecodeError, TypeError):
            print("Invalid JSON")
            pass

        # otherwise write keystrokes to PTY
        print(f"Writing {text_data=} to {self.master_file_descriptor=}")
        try:
            os.write(self.master_file_descriptor, text_data.encode())
        except Exception as e:
            print(f"Error writing to the file descriptor: {e=}")
            traceback.print_exc()
            await self.close()
        else:
            print(f"Wrote to {self.master_file_descriptor=}")
