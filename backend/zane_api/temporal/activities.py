import asyncio
from typing import List, Optional

from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    import docker
    import docker.errors
    from ..models import (
        Project,
        ArchivedProject,
        ArchivedDockerService,
    )
    from docker.models.networks import Network
    import requests
    from django.conf import settings
    from ..utils import strip_slash_if_exists


from .shared import (
    ProjectDetails,
    ArchivedProjectDetails,
    ArchivedServiceDetails,
    DeploymentDetails,
    URLDto,
)

docker_client: docker.DockerClient | None = None


def get_docker_client():
    """
    Get docker client
    """
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


def get_network_resource_name(project_id: str) -> str:
    return f"net-{project_id}"


def get_resource_labels(project_id: str, **kwargs):
    return {"zane-managed": "true", "zane-project": project_id, **kwargs}


def get_proxy_service():
    client = get_docker_client()
    services_list = client.services.list(filters={"label": ["zane.role=proxy"]})

    if len(services_list) == 0:
        raise docker.errors.NotFound("Proxy Service is not up")
    proxy_service = services_list[0]
    return proxy_service


def get_caddy_id_for_url(url: URLDto):
    normalized_path = strip_slash_if_exists(
        url.base_path, strip_end=True, strip_start=True
    ).replace("/", "-")

    if len(normalized_path) == 0:
        normalized_path = "*"

    return f"{url.domain}-{normalized_path}"


def get_swarm_service_name_for_deployment(deployment: DeploymentDetails):
    return f"srv-{deployment.project_id}-{deployment.service_id}-{deployment.id}"


class DockerSwarmActivities:
    DEFAULT_TIMEOUT_FOR_DOCKER_EVENTS = 30  # seconds

    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def create_project_network(self, payload: ProjectDetails) -> str:
        print(f"Running `create_project_network({payload=})`")
        try:
            project = await Project.objects.aget(id=payload.id)
        except Project.DoesNotExist:
            raise ApplicationError(
                f"Project with id=`{payload.id}` does not exist.", non_retryable=True
            )

        network = self.docker_client.networks.create(
            name=get_network_resource_name(project.id),
            scope="swarm",
            driver="overlay",
            labels=get_resource_labels(project.id),
            attachable=True,
        )
        print(f"`create_project_network({payload=})` returned {network.id=}")
        return network.id

    @activity.defn
    async def attach_network_to_proxy(self, network_id: str):
        print(f"Running `attach_network_to_proxy({network_id=})`")
        proxy_service = get_proxy_service()
        service_spec = proxy_service.attrs["Spec"]
        current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
        network_ids = set(net["Target"] for net in current_networks)
        network_ids.add(network_id)
        await asyncio.to_thread(proxy_service.update, networks=list(network_ids))
        print(f"Finished running `attach_network_to_proxy({network_id=})`")

    @activity.defn
    async def get_archived_project_services(
        self, project_details: ArchivedProjectDetails
    ) -> List[ArchivedServiceDetails]:
        try:
            archived_project = await ArchivedProject.objects.aget(pk=project_details.id)
        except ArchivedProject.DoesNotExist:
            raise ApplicationError(
                f"ArchivedProject with id=`{project_details.id}` does not exist.",
                non_retryable=True,
            )

        archived_docker_services = (
            ArchivedDockerService.objects.filter(project=archived_project)
            .select_related("project")
            .prefetch_related("volumes", "urls")
        )

        archived_services: List[ArchivedServiceDetails] = []
        async for service in archived_docker_services:
            archived_services.append(
                ArchivedServiceDetails(
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                        )
                        for url in service.urls.all()
                    ],
                    deployment_urls=service.deployment_urls,
                    deployments=[
                        DeploymentDetails(
                            id=deployment_hash,
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for deployment_hash in service.deployment_hashes
                    ],
                )
            )
        return archived_services

    @activity.defn
    async def unexpose_docker_service_from_http(
        self, service_details: ArchivedServiceDetails
    ):
        for url in service_details.urls:
            # get all the routes of the domain
            response = requests.get(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}/handle/0/routes",
                timeout=5,
            )

            if response.status_code != 404:
                current_routes: list[dict[str, dict]] = response.json()
                routes = list(
                    filter(
                        lambda route: route.get("@id") != get_caddy_id_for_url(url),
                        current_routes,
                    )
                )

                # delete the domain config when there are no routes for the domain anymore
                if len(routes) == 0:
                    requests.delete(
                        f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}",
                        timeout=5,
                    )
                else:
                    # in the other case, we just delete the caddy config
                    requests.delete(
                        f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{get_caddy_id_for_url(url)}",
                        timeout=5,
                    )

        for url in service_details.deployment_urls:
            requests.delete(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url}",
                timeout=5,
            )

    @activity.defn
    async def cleanup_docker_service_resources(
        self, service_details: ArchivedServiceDetails
    ):
        for deployment in service_details.deployments:
            try:
                swarm_service = self.docker_client.services.get(
                    get_swarm_service_name_for_deployment(deployment)
                )
            except docker.errors.NotFound:
                # we will assume the service has already been deleted
                pass
            else:
                swarm_service.scale(0)

                async def wait_for_service_to_be_down():
                    nonlocal swarm_service
                    print(f"waiting for service {swarm_service.name=} to be down...")
                    task_list = swarm_service.tasks()
                    while len(task_list) > 0:
                        print(
                            f"service {swarm_service.name=} is not down yet, "
                            + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
                        )
                        await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                        task_list = swarm_service.tasks()
                        continue
                    print(f"service {swarm_service.name=} is down, YAY !! 🎉")

                await wait_for_service_to_be_down()

                print("deleting volume list...")
                docker_volume_list = self.docker_client.volumes.list(
                    filters={
                        "label": [
                            f"{key}={value}"
                            for key, value in get_resource_labels(
                                deployment.project_id,
                                parent=deployment.service_id,
                            ).items()
                        ]
                    }
                )

                for volume in docker_volume_list:
                    volume.remove(force=True)
                print(f"Deleted {len(docker_volume_list)} volume(s), YAY !! 🎉")
                swarm_service.remove()
                print(f"Removed service. YAY !! 🎉")

    @activity.defn
    async def detach_network_from_proxy(
        self, project_details: ArchivedProjectDetails
    ) -> Optional[str]:
        try:
            network_associated_to_project = self.docker_client.networks.get(
                get_network_resource_name(project_id=project_details.original_id)
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                f"Network for {get_network_resource_name(project_id=project_details.original_id)}"
                f" for project `{project_details.original_id}` does not exist.",
                non_retryable=True,
            )

        proxy_service = get_proxy_service()
        service_spec = proxy_service.attrs["Spec"]
        current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
        network_ids = set(net["Target"] for net in current_networks)

        if network_associated_to_project.id in network_ids:
            network_ids.remove(network_associated_to_project.id)
            proxy_service.update(networks=list(network_ids))

        def wait_for_service_to_update():
            proxy = get_proxy_service()
            for event in self.docker_client.events(
                decode=True, filters={"service": proxy.id}
            ):
                print(f"⏩ received docker event: {event=}")
                if (
                    event["Type"] == "service"
                    and event.get("Action") == "update"
                    and event.get("Actor", {})
                    .get("Attributes", {})
                    .get("updatestate.new")
                    == "completed"
                ):
                    break

        await asyncio.to_thread(wait_for_service_to_update)
        return network_associated_to_project.id

    @activity.defn
    async def remove_project_network(self, project_details: ArchivedProjectDetails):
        try:
            network_associated_to_project: Network = self.docker_client.networks.get(
                get_network_resource_name(project_id=project_details.original_id)
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                f"Network for {get_network_resource_name(project_id=project_details.original_id)}"
                f" for project `{project_details.original_id}` does not exist.",
                non_retryable=True,
            )

        network_associated_to_project.remove()
