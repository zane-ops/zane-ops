from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import docker
    import docker.errors
    from asgiref.sync import sync_to_async
    from docker.models.networks import Network
    from ..models import Project

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


def attach_network_to_proxy(network: Network):
    proxy_service = get_proxy_service()
    service_spec = proxy_service.attrs["Spec"]
    current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
    network_ids = set(net["Target"] for net in current_networks)
    network_ids.add(network.id)
    proxy_service.update(networks=list(network_ids))


@activity.defn
@sync_to_async
def acreate_project_resources(project: Project):
    client = get_docker_client()
    network = client.networks.create(
        name=get_network_resource_name(project.id),
        scope="swarm",
        driver="overlay",
        labels=get_resource_labels(project.id),
        attachable=True,
    )
    attach_network_to_proxy(network)
