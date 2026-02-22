from typing import cast

from zane_api.models import Project, Environment, Deployment, Service
from temporal.helpers import get_swarm_service_name_for_deployment
import docker
import docker.errors
from zane_api.utils import DockerSwarmTask, Colors
import urllib.parse

from ..serializers import ContainerTerminalQuerySerializer
from ..exceptions import log_consumer_exceptions
from .container_terminal_consumer import GenericContainerTerminalConsumer


@log_consumer_exceptions
class DeploymentTerminalConsumer(GenericContainerTerminalConsumer):
    async def connect(self):
        kwargs = self.scope["url_route"]["kwargs"]  # type: ignore
        project_slug = kwargs["project_slug"]
        service_slug = kwargs["service_slug"]
        env_slug = kwargs.get("env_slug") or Environment.PRODUCTION_ENV_NAME
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

        print(f"Running with `{shell_cmd=}`")
        await self._run_cmd(shell_cmd, user)
