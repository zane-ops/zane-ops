# import json

import asyncio
import json
import os
import shlex

from channels.generic.websocket import AsyncWebsocketConsumer
from zane_api.models import Project, Environment, Deployment, Service
from zane_api.temporal.helpers import get_swarm_service_name_for_deployment
import docker
import docker.errors
from zane_api.utils import DockerSwarmTask, Colors
import pty
import urllib.parse
import fcntl
import termios
import struct


class WebShellConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docker_client = docker.from_env()

    async def connect(self):
        kwargs = self.scope["url_route"]["kwargs"]
        project_slug = kwargs["project_slug"]
        service_slug = kwargs["service_slug"]
        env_slug = kwargs.get("env_slug") or Environment.PRODUCTION_ENV
        deployment_hash = kwargs["deployment_hash"]

        await self.accept()

        try:
            project = await Project.objects.aget(slug=project_slug)
            environment = await Environment.objects.aget(
                name=env_slug.lower(), project=project
            )
            service = await Service.objects.aget(
                slug=service_slug, project=project, environment=environment
            )
            deployment: Deployment | None = await (
                Deployment.objects.filter(service=service, hash=deployment_hash)
                .select_related("service", "is_redeploy_of")
                .aget()
            )
        except Project.DoesNotExist:
            return await self.send(
                f"A project with the slug `{project_slug}` does not exist{Colors.ENDC}\n\r",
                close=True,
            )
        except Environment.DoesNotExist:
            return await self.send(
                f"{Colors.RED}An environment with the name `{env_slug}` does not exist in this project{Colors.ENDC}\n\r",
                close=True,
            )
        except Service.DoesNotExist:
            return await self.send(
                f"{Colors.RED}A service with the slug `{service_slug}` does not exist within the environment `{env_slug}` of the project `{project_slug}`{Colors.ENDC}\n\r",
                close=True,
            )
        except Deployment.DoesNotExist:
            return await self.send(
                f"{Colors.RED}A deployment with the hash `{deployment_hash}` does not exist for this service.{Colors.ENDC}\n\r",
                close=True,
            )
        try:
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=project.id,
                    service_id=service.id,
                )
            )
        except docker.errors.NotFound:
            return await self.send(
                f"{Colors.RED}No service exists for the deployment `{deployment_hash}`, either deploy or redeploy the service to create it.{Colors.ENDC}\n\r",
                close=True,
            )

        task_list = swarm_service.tasks(
            filters={
                "label": f"deployment_hash={deployment_hash}",
                "desired-state": "running",
            }
        )
        most_recent_swarm_task = DockerSwarmTask.from_dict(
            max(
                task_list,
                key=lambda task: task["Version"]["Index"],
            )
        )
        if most_recent_swarm_task.container_id is None:
            return await self.send(
                f"{Colors.RED}The container associated to the service `{deployment_hash}`, is not up, either deploy or redeploy the service to fix this.{Colors.ENDC}\n\r",
                close=True,
            )
        try:
            self.container = self.docker_client.containers.get(
                most_recent_swarm_task.container_id
            )
        except docker.errors.NotFound:
            return await self.send(
                f"{Colors.RED}The container associated to the service `{deployment_hash}`, is not up, either deploy or redeploy the service to fix this.{Colors.ENDC}\n\r",
                close=True,
            )

        # Parse the query string
        query_string = self.scope["query_string"].decode()  # Raw bytes -> string
        query_string = urllib.parse.unquote_plus(query_string)
        print(f"Received `{query_string=}`")
        params = urllib.parse.parse_qs(query_string)
        shell_cmd = params.get("cmd", ["/bin/sh"])[
            0
        ]  # Default to /bin/sh if not provided

        print(f"Running with `{shell_cmd=}`")

        # 1) Open a new local PTY
        master_fd, slave_fd = pty.openpty()

        # 2) Spawn `docker exec -it <container> <shell_cmd>` attached to that slave PTY
        cmd = [
            "docker",
            "exec",
            "-i",
            "-t",
            self.container.id,
            *shlex.split(shell_cmd),
        ]
        self.proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
        )
        os.close(slave_fd)  # we only need the master end
        self.master_fd = master_fd

        # 3) Hook the master FD into asyncio so we get output as it arrives
        loop = asyncio.get_running_loop()
        loop.add_reader(master_fd, self._on_pty_data)

        await self.send(
            text_data=f"{Colors.BLUE}Shell connected via {shell_cmd}{Colors.ENDC}\n\r"
        )

        # 4) Start a watcher that closes the WebSocket when the shell exits
        self.exit_watcher = asyncio.create_task(self._watch_proc())

    async def _watch_proc(self):
        # Wait until the subprocess (the shell) exits
        return_code = await self.proc.wait()
        # Inform the client
        await self.send(text_data=f"\n\r[Process exited with code {return_code}]\n\r")
        # Close the WS
        await self.close()

    def _on_pty_data(self):
        try:
            data = os.read(self.master_fd, 1024)
        except OSError:
            return
        if not data:
            return

        # send container output back to the WebSocket
        asyncio.get_event_loop().create_task(
            self.send(text_data=data.decode(errors="ignore"))
        )

    async def disconnect(self, code):
        """Close socket connection on disconnect."""
        # stop reading from the PTY
        loop = asyncio.get_running_loop()
        if hasattr(self, "master_fd"):
            loop.remove_reader(self.master_fd)
            os.close(self.master_fd)

        # terminate the subprocess cleanly
        if getattr(self, "proc", None):
            self.proc.terminate()  # send SIGTERM
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=1)
            except asyncio.TimeoutError:
                self.proc.kill()  # force-kill if needed
                await self.proc.wait()

    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ):
        """Send user input from WebSocket to the container."""
        print(f"Received: {text_data=}")

        if not text_data:
            return

        # check for resize messages
        try:
            msg = json.loads(text_data)
            if msg.get("type") == "resize":
                cols = msg.get("cols")
                rows = msg.get("rows")
                # perform ioctl on the PTY master
                size = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size)
                return
        except (json.JSONDecodeError, TypeError):
            pass

        # otherwise write keystrokes to PTY
        if text_data and hasattr(self, "master_fd"):
            os.write(self.master_fd, text_data.encode())
