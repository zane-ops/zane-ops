import asyncio
from typing import cast


from zane_api.models import Project, Environment, Deployment, Service
from temporal.helpers import get_swarm_service_name_for_deployment
from compose.models import ComposeStack
import docker
import docker.errors
from zane_api.utils import (
    DockerSwarmTask,
    Colors,
    NetworkAttachment,
    find_item_in_sequence,
)
from docker.models.services import Service as SwarmService


from .auth_terminal_consumer import AuthenticatedTerminalConsumer
from zane_api.models import WorkspaceRole
from zane_api.permissions import EffectiveAccess
import websockets
from django.conf import settings
from websockets import ClientConnection


class BaseContainerTerminalRelay(AuthenticatedTerminalConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docker_client = docker.from_env()
        self.websocket: ClientConnection | None = None

    async def get_node_worker_ip(self, node_id: str):
        services = self.docker_client.services.list(
            filters={
                "label": [
                    "com.docker.stack.namespace=zane",
                    "zane.role=node-worker",
                ],
                "mode": "global",
            }
        )
        if len(services) == 0:
            await self.send(
                f"{Colors.RED}Cannot open terminal: the ZaneOps node worker service was not found.{Colors.ENDC}\n\r"
                f"Container terminals require the `node-worker` service to be running in global mode "
                f"in the `zane` stack.\n\r"
                f"Check with: docker service ls --filter label=zane.role=node-worker\n\r",
                close=True,
            )
            return

        temporal_node_service = cast(SwarmService, services[0])
        worker_tasks = temporal_node_service.tasks(
            filters={"node": node_id, "desired-state": "running"}
        )
        if len(worker_tasks) == 0:
            return await self.send("", close=True)
        worker_task = DockerSwarmTask.from_dict(worker_tasks[0])

        def find_zane_network(network: NetworkAttachment):
            return network.Network.Spec.Name == "zane"

        network_data = find_item_in_sequence(
            find_zane_network, worker_task.NetworksAttachments
        )
        if network_data is not None and len(network_data.Addresses) > 0:
            return network_data.Addresses[0]
        else:
            await self.send(
                f"{Colors.RED}Cannot open terminal: the ZaneOps node worker has no address on the `zane` network.{Colors.ENDC}\n\r"
                f"The service exists but may not be attached to the network, or its tasks aren't running yet.\n\r"
                f"Check with: docker service ps --filter desired-state=running {temporal_node_service.name}\n\r",
                close=True,
            )
            return

    async def start_relay(self, node_id: str, container_id: str):
        worker_ip = await self.get_node_worker_ip(node_id)
        # querystring = urlencode()
        auth_headers = {"Authorization": f"Internal {settings.SECRET_KEY}"}
        uri = f"ws://{worker_ip}:{settings.TEMPORALIO_WORKER_WEBSOCKET_PORT}/container-terminal/{container_id}"

        # Parse the query string
        query_string = self.scope["query_string"].decode()  # Raw bytes -> string
        try:
            self.websocket = await websockets.connect(
                uri + "?" + query_string,
                additional_headers=auth_headers,
            )

            self.msg_watcher = asyncio.create_task(
                self._on_ws_message(websocket=self.websocket)
            )
        except Exception as e:
            return await self.send(
                f"{Colors.RED}Connection Error: {e}{Colors.ENDC}\n",
                close=True,
            )

    async def _on_ws_message(self, websocket: ClientConnection):
        while True:
            try:
                data = await websocket.recv(decode=True)
                await self.send(data)
            except websockets.exceptions.ConnectionClosed:
                return await self.send(
                    f"{Colors.GREY}Connection closed.{Colors.ENDC}\n",
                    close=True,
                )

    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ):
        """Send user input from WebSocket to the container."""
        print(f"Received: {text_data=}")
        data = bytes_data or text_data
        if self.websocket is not None and data:
            try:
                await self.websocket.send(message=data)
            except websockets.exceptions.ConnectionClosed:
                await self.send(
                    f"{Colors.GREY}Connection closed.{Colors.ENDC}\n",
                    close=True,
                )

    async def disconnect(self, code):
        if self.websocket is not None:
            await self.websocket.close(code)


class DeploymentContainerTerminalRelay(BaseContainerTerminalRelay):
    async def connect(self):
        await self.accept()

        membership = await self.check_for_workspace_roles(WorkspaceRole.MEMBER)
        if not membership:
            return await self.send(
                f"{Colors.RED}Permission Denied, closing websocket connection.{Colors.ENDC}\n\r",
                close=True,
            )

        kwargs = self.scope["url_route"]["kwargs"]  # type: ignore
        project_slug = kwargs["project_slug"]
        service_slug = kwargs["service_slug"]
        env_slug = kwargs.get("env_slug") or Environment.PRODUCTION_ENV_NAME
        deployment_hash = kwargs["deployment_hash"]
        container_id = kwargs["container_id"]

        try:
            project = await Project.objects.aget(
                slug=project_slug,
                id__in=EffectiveAccess.from_membership(
                    membership
                ).accessible_project_ids(),
            )
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
            swarm_service = cast(SwarmService, swarm_service)
        except docker.errors.NotFound:
            return await self.send(
                f"{Colors.RED}No service exists for the deployment `{deployment_hash}`, either deploy or redeploy the service to create it.{Colors.ENDC}\n\r",
                close=True,
            )

        task_list = [
            DockerSwarmTask.from_dict(task)
            for task in swarm_service.tasks(
                filters={
                    "label": f"deployment_hash={deployment_hash}",
                    "desired-state": "running",
                }
            )
        ]
        found_task = find_item_in_sequence(
            lambda t: t.container_id == container_id, task_list
        )
        if found_task is None:
            return await self.send(
                f"{Colors.RED}Service replica with container ID `{container_id}` not found for service `{service_slug}`.{Colors.ENDC}\n\r"
                f"{Colors.RED}The replica may have been removed or restarted since you last checked.{Colors.ENDC}\n\r"
                f"{Colors.RED}Refresh the service status to see the current list of replicas.{Colors.ENDC}\n\r",
                close=True,
            )

        if found_task.NodeID is None:
            return await self.send("", close=True)

        return await self.start_relay(found_task.NodeID, container_id)


class ComposeStackTerminalRelay(BaseContainerTerminalRelay):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docker_client = docker.from_env()

    async def connect(self):
        await self.accept()

        membership = await self.check_for_workspace_roles(WorkspaceRole.MEMBER)
        if not membership:
            return

        kwargs = self.scope["url_route"]["kwargs"]  # type: ignore
        project_slug = kwargs["project_slug"]
        env_slug = kwargs["env_slug"]
        stack_slug = kwargs["stack_slug"]
        service_name = kwargs["service_name"]
        container_id = kwargs["container_id"]

        try:
            project = await Project.objects.aget(
                slug=project_slug,
                id__in=EffectiveAccess.from_membership(
                    membership
                ).accessible_project_ids(),
            )
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

        task_list = [DockerSwarmTask.from_dict(task) for task in swarm_service.tasks()]

        found_task = find_item_in_sequence(
            lambda t: t.container_id == container_id, task_list
        )
        if found_task is None:
            return await self.send(
                f"{Colors.RED}Service replica with container ID `{container_id}` not found for service `{service_name}`.{Colors.ENDC}\n\r"
                f"{Colors.RED}The replica may have been removed or restarted since you last checked.{Colors.ENDC}\n\r"
                f"{Colors.RED}Refresh the service status to see the current list of replicas.{Colors.ENDC}\n\r",
                close=True,
            )
        if found_task.container_id is None:
            return await self.send(
                f"{Colors.RED}Replica `{container_id}` does not have a running container yet.{Colors.ENDC}\n\r"
                f"{Colors.RED}The container may still be starting or may have crashed.{Colors.ENDC}\n\r"
                f"{Colors.RED}Check the service status and logs for more details.{Colors.ENDC}\n\r",
                close=True,
            )

        if found_task.NodeID is None:
            return await self.send("", close=True)

        return await self.start_relay(found_task.NodeID, container_id)
