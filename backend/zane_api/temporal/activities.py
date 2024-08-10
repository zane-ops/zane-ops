import asyncio

from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    import docker
    import docker.errors
    from ..models import Project

from .shared import ProjectDetails

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


class BaseActivities:
    def __init__(self):
        self.docker_client = get_docker_client()


class DockerSwarmActivities(BaseActivities):

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
