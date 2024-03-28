import json
from typing import List, TypedDict, Literal

import docker
import docker.errors
import requests
from django.conf import settings
from docker.models.networks import Network
from docker.types import RestartPolicy, UpdateConfig, EndpointSpec
from rest_framework import status

from .models import (
    Project,
    Volume,
    DockerRegistryService,
    BaseService,
    DockerDeployment,
    PortConfiguration,
    URL,
)
from .utils import strip_slash_if_exists

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


def check_if_docker_image_exists(
    image: str, credentials: DockerAuthConfig = None
) -> bool:
    client = get_docker_client()
    try:
        client.images.get_registry_data(image, auth_config=credentials)
    except docker.errors.APIError:
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
        detach_network_from_proxy(network_associated_to_project)
        network_associated_to_project.remove()


def create_project_resources(project: Project):
    """
    Create the resources for the project, here it is mainly the project shared network
    """
    client = get_docker_client()
    network = client.networks.create(
        name=get_network_resource_name(project),
        scope="swarm",
        driver="overlay",
        labels=get_resource_labels(project),
        attachable=True,
    )
    attach_network_to_proxy(network)


def attach_network_to_proxy(network: Network):
    client = get_docker_client()
    service = client.services.get(settings.CADDY_PROXY_SERVICE)
    service_spec = service.attrs["Spec"]
    current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
    network_ids = set(net["Target"] for net in current_networks)
    network_ids.add(network.id)
    service.update(networks=list(network_ids))


def detach_network_from_proxy(network: Network):
    client = get_docker_client()
    service = client.services.get(settings.CADDY_PROXY_SERVICE)
    service_spec = service.attrs["Spec"]
    current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
    network_ids = set(net["Target"] for net in current_networks)
    if network.id in network_ids:
        network_ids.remove(network.id)
        service.update(networks=list(network_ids))


def check_if_port_is_available_on_host(port: int) -> bool:
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
    # TODO: Pull Image Tag (#44)
    client = get_docker_client()

    exposed_ports: dict[int, int] = {}
    endpoint_spec: EndpointSpec | None = None

    # We don't expose HTTP ports with docker because they will be handled by caddy directly
    http_ports = [80, 443]
    for port in service.ports.all():
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


def sort_proxy_routes(routes: list[dict[str, list[dict[str, list[str]]]]]):
    """
    This function implement the same ordering as caddy to pass to the caddy proxy API
    reference: https://caddyserver.com/docs/caddyfile/directives#sorting-algorithm
    This code is adapated from caddy source code : https://github.com/caddyserver/caddy/blob/ddb1d2c2b11b860f1e91b43d830d283d1e1363b2/caddyconfig/httpcaddyfile/directives.go#L495-L513
    """

    def path_specificity(route: dict[str, list[dict[str, list[str]]]]):
        path = route["match"][0]["path"][0]
        # Removing trailing '*' for comparison and determining the "real" length
        normalized_path = path.rstrip("*")
        path_length = len(normalized_path)

        # Using a tuple for comparison: first by the normalized length (longest first),
        # then by whether the original path ends with '*' (no wildcard is more specific),
        # and finally by the original path length in case of identical paths except for the wildcard
        return -path_length, path.endswith("*"), -len(path)

    # Sort the paths based on the specified criteria
    sorted_paths = sorted(routes, key=path_specificity)
    return sorted_paths


def get_caddy_request_for_domain(domain: str):
    return {
        "@id": domain,
        "match": [{"host": [domain]}],
        "handle": [
            {
                "handler": "subroute",
                "routes": [],
            }
        ],
        "terminal": True,
    }


def get_caddy_id_for_url(url: URL):
    normalized_path = strip_slash_if_exists(
        url.base_path, strip_end=True, strip_start=True
    ).replace("/", "-")

    return f"{url.domain}-{normalized_path}"


def get_caddy_request_for_url(
    url: URL, service: DockerRegistryService, http_port: PortConfiguration
):
    service_name = get_service_resource_name(service, service_type="docker")

    proxy_handlers = []

    if url.strip_prefix:
        proxy_handlers.append(
            {
                "handler": "rewrite",
                "strip_path_prefix": strip_slash_if_exists(
                    url.base_path, strip_end=True, strip_start=False
                ),
            }
        )

    proxy_handlers.append(
        {
            "flush_interval": -1,
            "handler": "reverse_proxy",
            "upstreams": [{"dial": f"{service_name}:{http_port.forwarded}"}],
        }
    )
    return {
        "@id": get_caddy_id_for_url(url),
        "handle": [
            {
                "handler": "subroute",
                "routes": [{"handle": proxy_handlers}],
            }
        ],
        "match": [
            {
                "path": [
                    f"{strip_slash_if_exists(url.base_path, strip_end=True, strip_start=False)}/*"
                ],
            }
        ],
    }


def expose_docker_service_to_http(service: DockerRegistryService) -> None:
    http_port: PortConfiguration = service.ports.filter(host__isnull=True).first()
    if http_port is None:
        raise Exception(
            f"Cannot expose service `{service.slug}` without a HTTP port exposed."
        )

    for url in service.urls.all():
        response = requests.get(f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}")

        # if the domain doesn't exist we create the config for the domain
        if response.status_code == status.HTTP_404_NOT_FOUND:
            requests.post(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/config/apps/http/servers/zane/routes",
                headers={"content-type": "application/json"},
                json=get_caddy_request_for_domain(url.domain),
            )

        # add logger if not exists
        response = requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/{url.domain}",
            headers={"content-type": "application/json", "accept": "application/json"},
        )
        if response.json() is None:
            requests.post(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/{url.domain}",
                data=json.dumps(""),
                headers={
                    "content-type": "application/json",
                    "accept": "application/json",
                },
            )

        # now we create the config for the URL
        response = requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{get_caddy_id_for_url(url)}"
        )
        if response.status_code == status.HTTP_404_NOT_FOUND:
            response = requests.get(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}"
            )
            domain_config = response.json()
            routes: list[dict] = domain_config["handle"][0]["routes"]
            routes.append(get_caddy_request_for_url(url, service, http_port))
            domain_config["handle"][0]["routes"] = sort_proxy_routes(routes)

            requests.patch(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}",
                headers={"content-type": "application/json"},
                json=domain_config,
            )
