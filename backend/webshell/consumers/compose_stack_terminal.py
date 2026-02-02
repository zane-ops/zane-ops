from typing import cast

from zane_api.models import Project, Environment
from compose.models import ComposeStack
import docker
import docker.errors
from zane_api.utils import DockerSwarmTask, Colors, find_item_in_sequence
import urllib.parse


from ..serializers import ContainerTerminalQuerySerializer
from ..exceptions import log_consumer_exceptions
from .container_terminal_consumer import GenericContainerTerminalConsumer


@log_consumer_exceptions
class ComposeStackTerminalConsumer(GenericContainerTerminalConsumer):
    async def connect(self):
        kwargs = self.scope["url_route"]["kwargs"]  # type: ignore
        project_slug = kwargs["project_slug"]
        env_slug = kwargs["env_slug"]
        stack_slug = kwargs["stack_slug"]
        service_name = kwargs["service_name"]
        task_id = kwargs["task_id"]

        await self.accept()

        try:
            project = await Project.objects.aget(slug=project_slug)
            environment = await Environment.objects.aget(
                name=env_slug.lower(), project=project
            )
            stack = await ComposeStack.objects.aget(
                environment=environment,
                project=project,
                slug=stack_slug,
            )
        except Project.DoesNotExist:
            return await self.send(
                f"{Colors.RED}A project with the slug `{project_slug}` does not exist{Colors.ENDC}\n\r",
                close=True,
            )
        except Environment.DoesNotExist:
            return await self.send(
                f"{Colors.RED}An environment with the name `{env_slug}` does not exist in this project{Colors.ENDC}\n\r",
                close=True,
            )
        except ComposeStack.DoesNotExist:
            return await self.send(
                f"{Colors.RED}A compose stack with the slug `{stack_slug}` does not exist in this environment{Colors.ENDC}\n\r",
                close=True,
            )
        try:
            swarm_service = self.docker_client.services.get(
                stack.get_full_computed_service_name(service_name)
            )
        except docker.errors.NotFound:
            return await self.send(
                f"{Colors.RED}No service named `{service_name}` found in the stack.{Colors.ENDC}\n\r",
                close=True,
            )

        service_mode = swarm_service.attrs["Spec"]["Mode"]

        # Determine mode type
        if "Global" in service_mode:
            mode_type = "global"
        elif "ReplicatedJob" in service_mode:
            mode_type = "replicated-job"
        elif "GlobalJob" in service_mode:
            mode_type = "global-job"
        else:
            # default is replicated
            mode_type = "replicated"

        # Determine status based on mode
        is_job = mode_type in ["replicated-job", "global-job"]

        if is_job:
            return await self.send(
                f"{Colors.RED}Cannot open a terminal for a job service.{Colors.ENDC}\n\r"
                f"{Colors.RED}Jobs are one-off tasks that exit after completion.{Colors.ENDC}\n\r"
                f"{Colors.RED}Try viewing the service logs instead to see the job output.{Colors.ENDC}\n\r",
                close=True,
            )

        task_list = [
            DockerSwarmTask.from_dict(task)
            for task in swarm_service.tasks(filters={"desired-state": "running"})
        ]

        found_task = find_item_in_sequence(
            lambda t: t.container_id == task_id, task_list
        )
        if found_task is None:
            return await self.send(
                f"{Colors.RED}Service replica `{task_id}` not found for service `{service_name}`.{Colors.ENDC}\n\r"
                f"{Colors.RED}The replica may have been removed or restarted since you last checked.{Colors.ENDC}\n\r"
                f"{Colors.RED}Refresh the service status to see the current list of replicas.{Colors.ENDC}\n\r",
                close=True,
            )
        if found_task.container_id is None:
            return await self.send(
                f"{Colors.RED}Container for replica `{task_id}` is not running.{Colors.ENDC}\n\r"
                f"{Colors.RED}The container may still be starting or may have crashed.{Colors.ENDC}\n\r"
                f"{Colors.RED}Check the service status and logs for more details.{Colors.ENDC}\n\r",
                close=True,
            )
        try:
            self.container = self.docker_client.containers.get(found_task.container_id)
        except docker.errors.NotFound:
            return await self.send(
                f"{Colors.RED}Container for replica `{task_id}` is not running.{Colors.ENDC}\n\r"
                f"{Colors.RED}The container may still be starting or may have crashed.{Colors.ENDC}\n\r"
                f"{Colors.RED}Check the service status and logs for more details.{Colors.ENDC}\n\r",
                close=True,
            )

        # Parse the query string
        query_string = self.scope["query_string"].decode()  # Raw bytes -> string
        query_string = urllib.parse.unquote_plus(query_string)
        print(f"Received `{query_string=}`")
        params = urllib.parse.parse_qs(query_string)
        serializer = ContainerTerminalQuerySerializer(data=params)
        if not serializer.is_valid():
            cmd = params.get("cmd")
            if cmd is not None:
                cmd = cmd[0]
            return await self.send(
                f"{Colors.RED}Invalid shell command `{cmd}`.{Colors.ENDC}\n\r",
                close=True,
            )

        data = cast(dict, serializer.data)
        shell_cmd = data["cmd"][0]
        user_args = data.get("user")
        user = None
        if user_args:
            user = user_args[0]

        await self._run_cmd(shell_cmd, user)
