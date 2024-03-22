from typing import List, TypedDict, Literal

import docker
import docker.errors
from docker.types import RestartPolicy, UpdateConfig, EndpointSpec

from .models import (
    Project,
    Volume,
    DockerRegistryService,
    BaseService,
    DockerDeployment,
)

docker_client: docker.DockerClient | None = None
DOCKER_HUB_REGISTRY_URL = "registry-1.docker.io/v2"


def get_docker_client():
    """
    Get docker client
    """
    global docker_client
    if docker_client is None:
        print("Recreate docker client")
        docker_client = docker.from_env()
    return docker_client


def get_network_resource_name(project: Project) -> str:
    ts_to_full_number = str(project.created_at.timestamp()).replace(".", "")
    return f"net-{project.slug}-{ts_to_full_number}"


def get_resource_labels(project: Project):
    return {"zane-managed": "true", "zane-project": project.slug}


class DockerImageResultFromRegistry(TypedDict):
    name: str
    description: str
    is_official: bool
    is_automated: bool


class DockerImageResult(TypedDict):
    full_image: str
    description: str


def search_images_docker_hub(term: str) -> List[DockerImageResult]:
    """
    List all images in registry starting with a certain term.
    """
    client = get_docker_client()
    result: List[DockerImageResultFromRegistry] = client.images.search(
        term=term, limit=30
    )
    images_to_return: List[DockerImageResult] = []

    for image in result:
        api_image_result = {}
        if image["is_official"]:
            api_image_result["full_image"] = f'library/{image["name"]}:latest'
        else:
            api_image_result["full_image"] = f'{image["name"]}:latest'
        api_image_result["description"] = image["description"]
        images_to_return.append(api_image_result)
    return images_to_return


def login_to_docker_registry(
    username: str, password: str, registry_url: str = DOCKER_HUB_REGISTRY_URL
):
    client = get_docker_client()
    client.login(
        username=username, password=password, registry=registry_url, reauth=True
    )


class DockerAuthConfig(TypedDict):
    username: str
    password: str


def pull_docker_image(image: str, auth: DockerAuthConfig = None):
    client = get_docker_client()
    client.images.pull(image, auth_config=auth)


def strip_slash_if_exists(url: str):
    if url.endswith("/"):
        return url[:-1]
    return url


def check_if_docker_image_exists(
    image: str, credentials: DockerAuthConfig = None
) -> bool:
    client = get_docker_client()
    try:
        client.images.get_registry_data(image, auth_config=credentials)
    except docker.errors.NotFound:
        return False
    else:
        return True


def cleanup_project_resources(project: Project):
    """
    Cleanup all resources attached to a project after it has been archived, which means :
    - cleaning up volumes (and deleting them in the DB & docker)
    - cleaning up CRONS
    - cleaning up Workers
    - cleaning up services (and deleting the attached volumes)
    - cleaning up docker networks
    - ... (TODO)

    TODO : we will need to cleanup :
      - services
      - workers &
      - CRONs
      - volumes
    """
    client = get_docker_client()

    try:
        network_associated_to_project = client.networks.get(
            get_network_resource_name(project)
        )
    except docker.errors.NotFound:
        # We will assume the network has been deleted before
        pass
    else:
        network_associated_to_project.remove()


def create_project_resources(project: Project):
    """
    Create the resources for the project, here it is mainly the project shared network
    """
    client = get_docker_client()
    client.networks.create(
        name=get_network_resource_name(project),
        scope="swarm",
        driver="overlay",
        labels=get_resource_labels(project),
        attachable=True,
    )


def check_if_port_is_available(port: int) -> bool:
    client = get_docker_client()
    try:
        client.containers.run(
            image="nginx:alpine",
            ports={"80/tcp": ("0.0.0.0", port)},
            command="echo hello world",
            remove=True,
        )
    except docker.errors.APIError:
        return False
    else:
        return True


def get_volume_resource_name(volume: Volume):
    ts_to_full_number = str(volume.created_at.timestamp()).replace(".", "")
    return f"vol-{volume.project.slug}-{volume.slug}-{ts_to_full_number}"


def create_docker_volume(volume: Volume):
    client = get_docker_client()

    client.volumes.create(
        name=get_volume_resource_name(volume),
        driver="local",
        labels=get_resource_labels(volume.project),
    )


def remove_docker_volume(volume: Volume):
    client = get_docker_client()
    try:
        docker_volume = client.volumes.get(get_volume_resource_name(volume))
    except docker.errors.NotFound:
        # We will assume the volume has been deleted before
        pass
    else:
        docker_volume.remove(force=True)


def get_docker_volume_size(volume: Volume) -> int:
    client = get_docker_client()
    docker_volume_name = get_volume_resource_name(volume)

    result: bytes = client.containers.run(
        image="alpine",
        command="du -sb /data",
        volumes={docker_volume_name: {"bind": "/data", "mode": "ro"}},
        remove=True,
    )
    size_string, _ = result.decode(encoding="utf-8").split("\t")
    return int(size_string)


def get_service_resource_name(
    service: BaseService, service_type: Literal["docker"] | Literal["git"]
):
    ts_to_full_number = str(service.created_at.timestamp()).replace(".", "")
    abbreviated_type = "dk" if service_type == "docker" else "git"
    return f"ser-{abbreviated_type}-{service.project.slug}-{service.slug}-{ts_to_full_number}"


def create_service_from_docker_registry(
    service: DockerRegistryService, deployment: DockerDeployment
):
    client = get_docker_client()

    exposed_ports: dict[int, int] = {}
    endpoint_spec: EndpointSpec | None = None

    # We don't expose HTTP ports with docker because they will be handled by caddy directly
    http_ports = [80, 443]
    for port in service.port_config.all():
        if port.host not in http_ports and port.host is not None:
            exposed_ports[port.host] = port.forwarded

    if len(exposed_ports) > 0:
        endpoint_spec = EndpointSpec(ports=exposed_ports)

    mounts: list[str] = []
    for volume in service.volumes.all():
        docker_volume = client.volumes.get(get_volume_resource_name(volume))
        mounts.append(f"{docker_volume.name}:{volume.containerPath}:rw")

    envs: list[str] = [
        f"{env.key}={env.value}" for env in deployment.env_variables.all()
    ]

    client.services.create(
        image=service.image,
        name=get_service_resource_name(service, "docker"),
        mounts=mounts,
        endpoint_spec=endpoint_spec,
        env=envs,
        labels=get_resource_labels(service.project),
        command=service.command,
        networks=[get_network_resource_name(service.project)],
        restart_policy=RestartPolicy(
            condition="on-failure",
            max_attempts=3,
            delay=5,
        ),
        update_config=UpdateConfig(
            parallelism=1,
            delay=5,
            monitor=10,
            order="start-first",
            failure_action="rollback",
        ),
    )
