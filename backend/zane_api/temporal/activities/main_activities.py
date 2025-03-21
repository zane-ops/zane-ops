import asyncio
import json
from datetime import timedelta
import re
from typing import Any, Coroutine, List, Optional, TypedDict

from rest_framework import status
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError


import platform
from ..main import create_schedule, delete_schedule, pause_schedule, unpause_schedule

with workflow.unsafe.imports_passed_through():
    from ..schedules import (
        MonitorDockerDeploymentWorkflow,
        GetDockerDeploymentStatsWorkflow,
    )
    from search.loki_client import LokiSearchClient
    from search.dtos import RuntimeLogDto, RuntimeLogLevel, RuntimeLogSource
    import docker
    import docker.errors
    from ...models import (
        Project,
        ArchivedProject,
        ArchivedDockerService,
        DockerDeployment,
        HealthCheck,
        URL,
        DockerDeploymentChange,
    )
    from docker.models.services import Service
    from urllib3.exceptions import HTTPError
    from requests import RequestException
    import requests
    from docker.types import (
        EndpointSpec,
        NetworkAttachmentConfig,
        RestartPolicy,
        Resources,
        UpdateConfig,
        ConfigReference,
        Healthcheck as DockerHealthcheckType,
    )
    from django.conf import settings
    from django.utils import timezone
    from time import monotonic
    from django.db.models import Q, Case, When, Value, F
    from ...utils import (
        strip_slash_if_exists,
        find_item_in_list,
        format_seconds,
        DockerSwarmTask,
        DockerSwarmTaskState,
        Colors,
        cache_result,
        convert_value_to_bytes,
        escape_ansi,
        excerpt,
    )
    from ..semaphore import AsyncSemaphore

from ...dtos import (
    ConfigDto,
    DockerServiceSnapshot,
    URLDto,
    HealthCheckDto,
    VolumeDto,
)
from ..shared import (
    DeploymentCreateConfigsResult,
    ProjectDetails,
    EnvironmentDetails,
    ArchivedProjectDetails,
    ArchivedServiceDetails,
    SimpleDeploymentDetails,
    DockerDeploymentDetails,
    DeploymentHealthcheckResult,
    HealthcheckDeploymentDetails,
    DeploymentCreateVolumesResult,
    DeploymentURLDto,
)

docker_client: docker.DockerClient | None = None
SERVER_RESOURCE_LIMIT_COMMAND = (
    "sh -c 'nproc && grep MemTotal /proc/meminfo | awk \"{print \\$2 * 1024}\"'"
)
VOLUME_SIZE_COMMAND = "sh -c 'df -B1 /mnt | tail -1 | awk \"{{print \\$2}}\"'"
ONE_HOUR = 3600  # seconds


def get_docker_volume_size_in_bytes(volume_id: str) -> int:
    client = get_docker_client()
    docker_volume_name = get_volume_resource_name(volume_id)

    result: bytes = client.containers.run(
        image="alpine",
        command="du -sb /data",
        volumes={docker_volume_name: {"bind": "/data", "mode": "ro"}},
        remove=True,
    )
    size_string, _ = result.decode(encoding="utf-8").split("\t")
    return int(size_string)


def get_docker_client():
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


def check_if_port_is_available_on_host(port: int) -> bool:
    client = get_docker_client()
    try:
        client.containers.run(
            image="busybox",
            ports={"80/tcp": ("0.0.0.0", port)},
            command="echo hello world",
            remove=True,
        )
    except docker.errors.APIError:
        return False
    else:
        return True


def check_if_docker_image_exists(
    image: str, credentials: dict[str, Any] | None = None
) -> bool:
    client = get_docker_client()
    try:
        client.images.get_registry_data(image, auth_config=credentials)
    except docker.errors.APIError:
        return False
    else:
        return True


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
    result: List[DockerImageResultFromRegistry] = []
    try:
        result = client.images.search(term=term, limit=30)
    except docker.errors.APIError:
        pass
    images_to_return: List[DockerImageResult] = []

    for image in result:
        images_to_return.append(
            {
                "full_image": image["name"],
                "description": image["description"],
            }
        )
    return images_to_return


def get_network_resource_name(project_id: str) -> str:
    return f"net-{project_id}"


def get_env_network_resource_name(env_id: str, project_id: str) -> str:
    return f"net-{project_id}-{env_id}"


def get_resource_labels(project_id: str, **kwargs):
    return {"zane-managed": "true", "zane-project": project_id, **kwargs}


def get_volume_resource_name(volume_id: str):
    return f"vol-{volume_id}"


def get_config_resource_name(config_id: str, version: int):
    return f"cf-{config_id}-{version}"


def get_swarm_service_name_for_deployment(
    deployment_hash: str,
    project_id: str,
    service_id: str,
):
    return f"srv-{project_id}-{service_id}-{deployment_hash}"


async def deployment_log(
    deployment: (
        DockerDeploymentDetails
        | DeploymentHealthcheckResult
        | DeploymentCreateVolumesResult
        | DeploymentCreateConfigsResult
    ),
    message: str,
    error=False,
):
    current_time = timezone.now()
    print(f"[{current_time.isoformat()}]: {message}")

    match deployment:
        case DockerDeploymentDetails():
            deployment_id = deployment.hash
            service_id = deployment.service.id
        case (
            DeploymentCreateVolumesResult()
            | DeploymentHealthcheckResult()
            | DeploymentCreateConfigsResult()
        ):
            deployment_id = deployment.deployment_hash
            service_id = deployment.service_id
        case _:
            raise TypeError(f"unsupported type {type(deployment)}")
    search_client = LokiSearchClient(host=settings.LOKI_HOST)

    MAX_COLORED_CHARS = 1000
    search_client.insert(
        document=RuntimeLogDto(
            source=RuntimeLogSource.SYSTEM,
            level=RuntimeLogLevel.INFO if not error else RuntimeLogLevel.ERROR,
            content=excerpt(message, MAX_COLORED_CHARS),
            content_text=excerpt(escape_ansi(message), MAX_COLORED_CHARS),
            time=current_time,
            created_at=current_time,
            deployment_id=deployment_id,
            service_id=service_id,
        ),
    )


@cache_result(ttl=ONE_HOUR)
def get_server_resource_limits() -> tuple[int, int]:
    client = get_docker_client()

    result: bytes = client.containers.run(
        image="busybox",
        command=SERVER_RESOURCE_LIMIT_COMMAND,
        remove=True,
    )
    no_of_cpus, max_memory_in_bytes = (
        result.decode(encoding="utf-8").strip().split("\n")
    )
    return int(no_of_cpus), int(max_memory_in_bytes)


class ZaneProxyEtagError(Exception):
    pass


class ZaneProxyClient:
    MAX_ETAG_ATTEMPTS = 3

    @classmethod
    def get_service(cls):
        client = get_docker_client()

        services_list = client.services.list(filters={"label": ["zane.role=proxy"]})

        if len(services_list) == 0:
            raise docker.errors.NotFound("Proxy Service is not up")
        proxy_service = services_list[0]
        return proxy_service

    @classmethod
    def _get_id_for_deployment(cls, deployment_hash: str, domain: str):
        return f"{deployment_hash}-{domain}"

    @classmethod
    def get_uri_for_deployment(cls, deployment_hash: str, domain: str):
        return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{cls._get_id_for_deployment(deployment_hash, domain)}"

    @classmethod
    def _get_request_for_deployment_url(
        cls, deployment: DockerDeploymentDetails, url: DeploymentURLDto
    ):
        service_name = get_swarm_service_name_for_deployment(
            deployment_hash=deployment.hash,
            project_id=deployment.service.project_id,
            service_id=deployment.service.id,
        )

        # This gnarly config object is so that only authenticated
        # users can have access to this deployment
        # It proxies the request to the API that checks that the user is authenticated before allowing the request
        protect_deployment_proxy_handler = {
            "handle_response": [
                {
                    "match": {"status_code": [2]},
                    "routes": [
                        {
                            "handle": [
                                {
                                    "handler": "headers",
                                    "request": {},
                                }
                            ]
                        }
                    ],
                }
            ],
            "handler": "reverse_proxy",
            "headers": {
                "request": {
                    "set": {
                        "X-Forwarded-Method": ["{http.request.method}"],
                        "X-Forwarded-Uri": ["{http.request.uri}"],
                    }
                }
            },
            "rewrite": {
                "method": "GET",
                "uri": "/api/auth/me/with-token",
            },
            "upstreams": [{"dial": settings.ZANE_FRONT_SERVICE_INTERNAL_DOMAIN}],
        }

        return {
            "@id": cls._get_id_for_deployment(deployment.hash, url.domain),
            "match": [{"host": [url.domain]}],
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [
                        {
                            "handle": [
                                protect_deployment_proxy_handler,
                                {
                                    "handler": "encode",
                                    "encodings": {"gzip": {}},
                                    "prefer": ["gzip"],
                                },
                                {
                                    "flush_interval": -1,
                                    "handler": "reverse_proxy",
                                    "upstreams": [
                                        {"dial": f"{service_name}:{url.port}"}
                                    ],
                                },
                            ]
                        }
                    ],
                }
            ],
        }

    @classmethod
    def _get_id_for_service_url(cls, service_id: str, url: URLDto | URL):
        normalized_path = strip_slash_if_exists(
            url.base_path, strip_end=True, strip_start=True
        ).replace("/", "-")

        if len(normalized_path) == 0:
            normalized_path = "*"
        return f"{service_id}-{url.domain}-{normalized_path}"

    @classmethod
    def _sort_routes(cls, routes: list[dict[str, list[dict[str, list[str]]]]]):
        """
        This function implement the same ordering as caddy to pass to the caddy proxy API
        reference: https://caddyserver.com/docs/caddyfile/directives#sorting-algorithm
        This code is adapated from caddy source code : https://github.com/caddyserver/caddy/blob/ddb1d2c2b11b860f1e91b43d830d283d1e1363b2/caddyconfig/httpcaddyfile/directives.go#L495-L513
        """

        def custom_order(route: dict[str, list[dict[str, list[str]]]]):
            route_match = route.get("match")
            route_id = route.get("@id")

            if route_match is None:
                # This is the default 404 catchall for zaneops, we want to put this route at the end
                return 3  # Highest value to sort at the end
            elif route_id == "frontend.zaneops.internal":
                # Put the frontend just before the catchall
                return 2
            elif route_id == "api.zaneops.internal":
                # Put the API before both frontend and catchall
                return 1
            else:
                return 0  # Default for other routes

        def path_specificity(route: dict[str, list[dict[str, list[str]]]]):
            if "match" not in route or not route["match"]:
                return (
                    float("inf"),
                    True,
                    float("inf"),
                )  # Least priority for routes with no match

            path = route["match"][0].get("path", [""])[0]
            # Removing trailing '*' for comparison and determining the "real" length
            normalized_path = path.rstrip("*")
            path_length = len(normalized_path)

            return -path_length, path.endswith("*"), -len(path)

        def host_specificity(route: dict[str, list[dict[str, list[str]]]]):
            if "match" not in route or not route["match"]:
                return "~"  # Ensures routes with no match are sorted last

            host = route["match"][0].get("host", [""])[0]
            return host

        return sorted(
            routes,
            key=lambda route: (
                # First, sort by path specificity,
                path_specificity(route),
                # Then sort by host, grouping the same hosts together
                host_specificity(route),
                # Then apply a custom order that put the catchall at the end
                custom_order(route),
            ),
        )

    @classmethod
    def _get_request_for_service_url(
        cls,
        url: URLDto,
        current_deployment: DockerDeploymentDetails,
        previous_deployment: DockerDeployment | None,
    ):
        service = current_deployment.service
        http_port = url.associated_port
        blue_hash = None
        green_hash = None

        if current_deployment.slot == "BLUE":
            blue_hash = current_deployment.hash
        elif current_deployment.slot == "GREEN":
            green_hash = current_deployment.hash

        if previous_deployment is not None:
            if previous_deployment.slot == "BLUE":
                blue_hash = previous_deployment.hash
            elif previous_deployment.slot == "GREEN":
                green_hash = previous_deployment.hash

        proxy_handlers = [
            {
                "handler": "log_append",
                "key": "zane_service_id",
                "value": service.id,
            },
            {
                "handler": "log_append",
                "key": "zane_deployment_blue_hash",
                "value": blue_hash,
            },
            {
                "handler": "log_append",
                "key": "zane_deployment_green_hash",
                "value": green_hash,
            },
            {
                "handler": "log_append",
                "key": "zane_deployment_upstream",
                "value": "{http.reverse_proxy.upstream.hostport}",
            },
            {
                "handler": "log_append",
                "key": "zane_request_id",
                "value": "{http.request.uuid}",
            },
            {
                "handler": "headers",
                "response": {
                    "add": {
                        "x-zane-request-id": ["{http.request.uuid}"],
                        "x-zane-dpl-hash": [current_deployment.hash],
                        "x-zane-dpl-slot": [current_deployment.slot.lower()],
                    },
                },
                "request": {
                    "add": {
                        "x-request-id": ["{http.request.uuid}"],
                    },
                },
            },
        ]

        if url.strip_prefix:
            proxy_handlers.append(
                {
                    "handler": "rewrite",
                    "strip_path_prefix": strip_slash_if_exists(
                        url.base_path, strip_end=True, strip_start=False
                    ),
                }
            )

        if url.redirect_to is not None:
            proxy_handlers.append(
                {
                    "handler": "static_response",
                    "headers": {
                        "Location": [f"{url.redirect_to.url}{{http.request.uri}}"]
                    },
                    "status_code": (
                        status.HTTP_308_PERMANENT_REDIRECT
                        if url.redirect_to.permanent
                        else status.HTTP_307_TEMPORARY_REDIRECT
                    ),
                }
            )
        else:
            # Gzip encoding
            proxy_handlers.append(
                {
                    "handler": "encode",
                    "encodings": {"gzip": {}},
                    "prefer": ["gzip"],
                },
            )

            proxy_handlers.append(
                {
                    "handler": "reverse_proxy",
                    "flush_interval": -1,
                    "load_balancing": {
                        "retries": 2,
                    },
                    "upstreams": [
                        {"dial": f"{current_deployment.network_alias}:{http_port}"},
                    ],
                }
            )
        return {
            "@id": cls._get_id_for_service_url(service.id, url),
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [{"handle": proxy_handlers}],
                }
            ],
            "match": [
                {
                    "path": [
                        (
                            "/*"
                            if url.base_path == "/"
                            else f"{strip_slash_if_exists(url.base_path, strip_end=True, strip_start=False)}*"
                        )
                    ],
                    "host": [url.domain],
                }
            ],
        }

    @classmethod
    def insert_deployment_urls(cls, deployment: DockerDeploymentDetails):
        for url in deployment.urls:
            response = requests.get(
                cls.get_uri_for_deployment(deployment.hash, url.domain),
                timeout=5,
            )

            # if the domain doesn't exist we create the config for the domain
            if response.status_code == status.HTTP_404_NOT_FOUND:
                deployment_url = find_item_in_list(
                    lambda u: u.domain == url.domain, deployment.urls
                )
                if deployment_url is not None:
                    requests.put(
                        f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes/0",
                        headers={"content-type": "application/json"},
                        json=cls._get_request_for_deployment_url(
                            deployment, deployment_url
                        ),
                        timeout=5,
                    )

    @classmethod
    def upsert_service_url(
        cls,
        url: URLDto,
        current_deployment: DockerDeploymentDetails,
        previous_deployment: DockerDeployment | None,
    ) -> bool:
        attempts = 0

        while attempts < cls.MAX_ETAG_ATTEMPTS:
            attempts += 1
            # now we create or modify the config for the URL
            response = requests.get(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes", timeout=5
            )
            etag = response.headers.get("etag")

            routes: list[dict[str, dict]] = [
                route
                for route in response.json()
                if route["@id"]
                != cls._get_id_for_service_url(current_deployment.service.id, url)
            ]
            new_url = cls._get_request_for_service_url(
                url, current_deployment, previous_deployment
            )
            routes.append(new_url)
            routes = cls._sort_routes(routes)  # type: ignore

            response = requests.patch(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes",
                headers={"content-type": "application/json", "If-Match": etag},
                json=routes,
                timeout=5,
            )
            if response.status_code == status.HTTP_412_PRECONDITION_FAILED:
                continue
            return True

        raise ZaneProxyEtagError(
            f"Failed inserting the url {url} in the proxy because `Etag` precondtion failed"
        )

    @classmethod
    def get_uri_for_service_url(cls, service_id: str, url: URLDto | URL):
        return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{cls._get_id_for_service_url(service_id, url)}"

    @classmethod
    def remove_service_url(cls, service_id: str, url: URLDto):
        attempts = 0

        while attempts < cls.MAX_ETAG_ATTEMPTS:
            attempts += 1
            response = requests.get(
                cls.get_uri_for_service_url(service_id, url),
                timeout=5,
            )
            etag = response.headers.get("etag")

            if response.status_code != status.HTTP_404_NOT_FOUND:
                response = requests.delete(
                    cls.get_uri_for_service_url(service_id, url),
                    headers={"If-Match": etag},
                    timeout=5,
                )
                if response.status_code == status.HTTP_412_PRECONDITION_FAILED:
                    continue
            return

        raise ZaneProxyEtagError(
            f"Failed deleting the url {url} in the proxy because `Etag` precondtion failed"
        )

    @classmethod
    def cleanup_old_service_urls(cls, deployment: DockerDeploymentDetails):
        """
        Remove old URLs that are not attached to the service anymore
        """
        service = deployment.service
        response = requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes", timeout=5
        )
        service_url_ids = [
            cls._get_id_for_service_url(service.id, url) for url in service.urls
        ]
        for route in response.json():
            if (
                route["@id"].startswith(service.id)
                and route["@id"] not in service_url_ids
            ):
                requests.delete(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{route['@id']}",
                    timeout=5,
                )

    @classmethod
    def remove_deployment_url(cls, deployment_hash: str, domain: str):
        requests.delete(
            cls.get_uri_for_deployment(deployment_hash, domain),
            timeout=5,
        )


DEPLOY_SEMAPHORE_KEY = "deploy-workflow"


@activity.defn
async def acquire_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    )
    await semaphore.acquire()


@activity.defn
async def release_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    )
    await semaphore.release()


@activity.defn
async def lock_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=timedelta(
            minutes=5
        ),  # this is to prevent the system cleanup from blocking for too long
    )
    await semaphore.acquire_all()


@activity.defn
async def reset_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=timedelta(
            minutes=5
        ),  # this is to prevent the system cleanup from blocking for too long
    )
    await semaphore.reset()


class SystemCleanupActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def cleanup_images(self) -> dict:
        return self.docker_client.images.prune(filters={"dangling": False})

    @activity.defn
    async def cleanup_volumes(self) -> dict:
        return self.docker_client.volumes.prune(
            filters={
                "all": True,
                "label!": ["zane-managed"],
            }
        )

    @activity.defn
    async def cleanup_containers(self) -> dict:
        return self.docker_client.containers.prune()

    @activity.defn
    async def cleanup_networks(self) -> dict:
        return self.docker_client.networks.prune(
            filters={
                "label!": ["zane-managed"],
            }
        )


def replace_env_variables(text: str, replacements: dict[str, str]):
    """
    Replaces placeholders in the format {{env.VARIABLE_NAME}} with predefined values.

    Only replaces variable names that match the regex: ^[A-Za-z_][A-Za-z0-9_]*$

    :param text: The input string containing placeholders.
    :param replacements: A dictionary mapping variable names to their replacement values.
    :return: The modified string with replacements applied.
    """
    placeholder_pattern = r"\{\{env\.([A-Za-z_][A-Za-z0-9_]*)\}\}"

    def replacer(match: re.Match[str]):
        var_name = match.group(1)
        return replacements.get(var_name, match.group(0))  # Keep original if not found

    return re.sub(placeholder_pattern, replacer, text)


class DockerSwarmActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def create_project_network(self, payload: ProjectDetails) -> str:
        try:
            project = await Project.objects.aget(id=payload.id)
        except Project.DoesNotExist:
            raise ApplicationError(
                f"Project with id=`{payload.id}` does not exist.", non_retryable=True
            )

        production_env = await project.aproduction_env
        network = self.docker_client.networks.create(
            name=get_env_network_resource_name(
                production_env.id, project_id=project.id
            ),
            scope="swarm",
            driver="overlay",
            labels=get_resource_labels(project.id, is_production="True"),
            attachable=True,
        )
        return network.id  # type:ignore

    @activity.defn
    async def create_environment_network(self, payload: EnvironmentDetails) -> str:
        network = self.docker_client.networks.create(
            name=get_env_network_resource_name(
                payload.id, project_id=payload.project_id
            ),
            scope="swarm",
            driver="overlay",
            labels=get_resource_labels(payload.project_id),
            attachable=True,
        )
        return network.id  # type:ignore

    @activity.defn
    async def delete_environment_network(self, payload: EnvironmentDetails):
        try:
            network = self.docker_client.networks.get(
                get_env_network_resource_name(payload.id, project_id=payload.project_id)
            )
        except docker.errors.NotFound:
            pass  # network has probably been already delete
        else:
            network.remove()

    @activity.defn
    async def get_archived_project_services(
        self, project_details: ArchivedProjectDetails
    ) -> List[ArchivedServiceDetails]:
        try:
            archived_project: ArchivedProject = await ArchivedProject.objects.aget(
                pk=project_details.id
            )
        except ArchivedProject.DoesNotExist:
            raise ApplicationError(
                f"ArchivedProject with id=`{project_details.id}` does not exist.",
                non_retryable=True,
            )

        archived_docker_services = (
            ArchivedDockerService.objects.filter(project=archived_project)
            .select_related("project")
            .prefetch_related("volumes", "urls", "configs")
        )

        archived_services: List[ArchivedServiceDetails] = []
        async for service in archived_docker_services:
            archived_services.append(
                ArchivedServiceDetails(
                    original_id=service.original_id,
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                            id=url.original_id,
                        )
                        for url in service.urls.all()
                    ],
                    project_id=archived_project.original_id,
                    deployments=[
                        SimpleDeploymentDetails(
                            hash=dpl.get("hash"),  # type: ignore
                            urls=dpl.get("urls") or [],  # type: ignore
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for dpl in service.deployments
                    ],
                )
            )
        return archived_services

    @activity.defn
    async def get_archived_env_services(
        self, environment: EnvironmentDetails
    ) -> List[ArchivedServiceDetails]:
        archived_docker_services = (
            ArchivedDockerService.objects.filter(environment_id=environment.id)
            .select_related("project")
            .prefetch_related("volumes", "urls", "configs")
        )

        archived_services: List[ArchivedServiceDetails] = []
        async for service in archived_docker_services:
            archived_services.append(
                ArchivedServiceDetails(
                    original_id=service.original_id,
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                            id=url.original_id,
                        )
                        for url in service.urls.all()
                    ],
                    project_id=service.project.original_id,
                    deployments=[
                        SimpleDeploymentDetails(
                            hash=dpl.get("hash"),  # type: ignore
                            urls=dpl.get("urls") or [],  # type: ignore
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for dpl in service.deployments
                    ],
                )
            )
        return archived_services

    @activity.defn
    async def cleanup_docker_service_resources(
        self, service_details: ArchivedServiceDetails
    ):
        for deployment in service_details.deployments:
            service_name = get_swarm_service_name_for_deployment(
                deployment_hash=deployment.hash,
                service_id=deployment.service_id,
                project_id=deployment.project_id,
            )
            try:
                swarm_service = self.docker_client.services.get(service_name)
            except docker.errors.NotFound:
                print(f"service `{service_name}` not found")
                # we will assume the service has already been deleted
                pass
            else:
                swarm_service.scale(0)

                async def wait_for_service_deployment_to_be_down():
                    nonlocal swarm_service
                    print(f"waiting for service {swarm_service.name=} to be down...")
                    task_list = swarm_service.tasks(
                        filters={"desired-state": "running"}
                    )
                    while len(task_list) > 0:
                        print(
                            f"service {swarm_service.name=} is not down yet, "
                            + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
                        )
                        await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                        task_list = swarm_service.tasks(
                            filters={"desired-state": "running"}
                        )
                        continue
                    print(f"service {swarm_service.name=} is down, YAY !! 🎉")

                await wait_for_service_deployment_to_be_down()

                swarm_service.remove()
                print("Removed service. YAY !! 🎉")
                try:
                    await asyncio.gather(
                        delete_schedule(deployment.monitor_schedule_id),
                        delete_schedule(deployment.metrics_schedule_id),
                    )
                except RPCError:
                    pass
        print("deleting volume list...")
        docker_volume_list = self.docker_client.volumes.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service_details.project_id,
                        parent=service_details.original_id,
                    ).items()
                ]
            }
        )

        for volume in docker_volume_list:
            volume.remove(force=True)
        print(f"Deleted {len(docker_volume_list)} volume(s), YAY !! 🎉")

        print("deleting config list...")
        docker_config_list = self.docker_client.configs.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service_details.project_id,
                        parent=service_details.original_id,
                    ).items()
                ]
            }
        )

        for config in docker_config_list:
            config.remove()
        print(f"Deleted {len(docker_config_list)} config(s), YAY !! 🎉")
        search_client = LokiSearchClient(
            host=settings.LOKI_HOST,
        )
        search_client.delete(
            query=dict(service_id=service_details.original_id),
        )

    @activity.defn
    async def remove_project_network(
        self, project_details: ArchivedProjectDetails
    ) -> List[str]:
        try:
            networks_associated_to_project = self.docker_client.networks.list(
                filters={
                    "label": [
                        f"{key}={value}"
                        for key, value in get_resource_labels(
                            project_id=project_details.original_id
                        ).items()
                    ]
                }
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                f"Network `{get_network_resource_name(project_id=project_details.original_id)}`"
                f" for project `{project_details.original_id}` does not exist.",
                non_retryable=True,
            )

        deleted_networks: List[str] = [net.name for net in networks_associated_to_project]  # type: ignore
        for network in networks_associated_to_project:
            network.remove()
        return deleted_networks

    @activity.defn
    async def prepare_deployment(self, deployment: DockerDeploymentDetails):
        try:
            await deployment_log(
                deployment,
                f"Preparing deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
            )
            docker_deployment: DockerDeployment = await DockerDeployment.objects.aget(
                hash=deployment.hash, service_id=deployment.service.id
            )
            if docker_deployment.status == DockerDeployment.DeploymentStatus.QUEUED:
                docker_deployment.status = DockerDeployment.DeploymentStatus.PREPARING
                docker_deployment.started_at = timezone.now()
                await docker_deployment.asave()
        except DockerDeployment.DoesNotExist:
            raise ApplicationError(
                "Cannot execute a deploy on a non existent deployment.",
                non_retryable=True,
            )

    @activity.defn
    async def toggle_cancelling_status(self, deployment: DockerDeploymentDetails):
        await deployment_log(
            deployment,
            f"Handling cancellation request for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        await DockerDeployment.objects.filter(hash=deployment.hash).aupdate(
            status=DockerDeployment.DeploymentStatus.CANCELLING,
        )

    @activity.defn
    async def save_cancelled_deployment(self, deployment: DockerDeploymentDetails):
        await DockerDeployment.objects.filter(hash=deployment.hash).aupdate(
            status=DockerDeployment.DeploymentStatus.CANCELLED,
            status_reason="Deployment cancelled.",
            finished_at=timezone.now(),
        )
        await deployment_log(
            deployment,
            f"Deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}"
            f" finished with status {Colors.GREY}{DockerDeployment.DeploymentStatus.CANCELLED}{Colors.ENDC}.",
        )

    @activity.defn
    async def finish_and_save_deployment(
        self, healthcheck_result: DeploymentHealthcheckResult
    ) -> tuple[str, str]:
        try:
            deployment = (
                await DockerDeployment.objects.filter(
                    hash=healthcheck_result.deployment_hash
                )
                .select_related("service")
                .afirst()
            )

            if deployment is None:
                raise DockerDeployment.DoesNotExist(
                    f"Docker deployment with hash='{healthcheck_result.deployment_hash}' does not exist."
                )

            deployment.status_reason = healthcheck_result.reason
            if (
                healthcheck_result.status == DockerDeployment.DeploymentStatus.HEALTHY
                or await deployment.service.deployments.acount() == 1  # type: ignore
            ):
                deployment.is_current_production = True

            deployment.status = (
                DockerDeployment.DeploymentStatus.HEALTHY
                if healthcheck_result.status
                == DockerDeployment.DeploymentStatus.HEALTHY
                else DockerDeployment.DeploymentStatus.FAILED
            )

            deployment.finished_at = timezone.now()
            await deployment.asave()

            if deployment.is_current_production:
                await deployment.service.deployments.filter(  # type: ignore
                    ~Q(hash=healthcheck_result.deployment_hash)
                ).aupdate(is_current_production=False)
                await deployment.service.deployments.filter(  # type: ignore
                    ~Q(hash=healthcheck_result.deployment_hash)
                    & Q(
                        status__in=[
                            DockerDeployment.DeploymentStatus.PREPARING,
                            DockerDeployment.DeploymentStatus.STARTING,
                            DockerDeployment.DeploymentStatus.RESTARTING,
                        ]
                    )
                    & (Q(started_at__isnull=True) | Q(finished_at__isnull=True)),
                ).aupdate(
                    finished_at=Case(
                        When(finished_at__isnull=True, then=Value(timezone.now())),
                        default=F("finished_at"),
                    ),
                    started_at=Case(
                        When(started_at__isnull=True, then=Value(timezone.now())),
                        default=F("started_at"),
                    ),
                    status=DockerDeployment.DeploymentStatus.REMOVED,
                )
        except DockerDeployment.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent deployment.",
                non_retryable=True,
            )
        else:
            status_color = (
                Colors.GREEN
                if deployment.status == DockerDeployment.DeploymentStatus.HEALTHY
                else Colors.RED
            )
            await deployment_log(
                healthcheck_result,
                f"Deployment {Colors.ORANGE}{healthcheck_result.deployment_hash}{Colors.ENDC}"
                f" finished with status {status_color}{deployment.status}{Colors.ENDC}.",
            )
            await deployment_log(
                healthcheck_result,
                f"Deployment {Colors.ORANGE}{healthcheck_result.deployment_hash}{Colors.ENDC}"
                f" finished with reason {Colors.GREY}{deployment.status_reason}{Colors.ENDC}.",
            )
            return deployment.status, deployment.status_reason  # type: ignore

    @activity.defn
    async def get_previous_production_deployment(
        self, deployment: DockerDeploymentDetails
    ) -> Optional[SimpleDeploymentDetails]:
        latest_production_deployment: DockerDeployment | None = await (
            DockerDeployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(is_current_production=True)
                & ~Q(hash=deployment.hash)
            )
            .order_by("-queued_at")
            .afirst()
        )

        if latest_production_deployment is not None:
            if (
                latest_production_deployment.service_snapshot.get("environment") is None  # type: ignore
            ):
                latest_production_deployment.service_snapshot["environment"] = (  # type: ignore
                    deployment.service.environment.to_dict()
                )
            return SimpleDeploymentDetails(
                hash=latest_production_deployment.hash,
                service_id=latest_production_deployment.service_id,  # type: ignore
                project_id=deployment.service.project_id,
                status=latest_production_deployment.status,
                urls=[url.domain async for url in latest_production_deployment.urls.all()],  # type: ignore
                service_snapshot=DockerServiceSnapshot.from_dict(
                    latest_production_deployment.service_snapshot  # type: ignore
                ),
            )
        return None

    @activity.defn
    async def get_previous_queued_deployment(self, deployment: DockerDeploymentDetails):
        next_deployment = (
            await DockerDeployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(status=DockerDeployment.DeploymentStatus.QUEUED)
            )
            .select_related("service", "service__environment")
            .order_by("queued_at")
            .afirst()
        )

        if next_deployment is not None:
            latest_deployment = (
                await next_deployment.service.alatest_production_deployment
            )
            next_deployment.slot = DockerDeployment.get_next_deployment_slot(
                latest_deployment
            )
            await next_deployment.asave()

            return await DockerDeploymentDetails.afrom_deployment(
                deployment=next_deployment
            )
        return None

    @activity.defn
    async def delete_previous_production_deployment_schedules(
        self, deployment: SimpleDeploymentDetails
    ):
        docker_deployment = (
            await DockerDeployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service_id
            )
            .select_related("service")
            .afirst()
        )

        if docker_deployment is not None:
            try:
                # delete schedule
                await asyncio.gather(
                    delete_schedule(
                        id=docker_deployment.monitor_schedule_id,
                    ),
                    delete_schedule(
                        id=docker_deployment.metrics_schedule_id,
                    ),
                )
                print(
                    f"Deleted previous production deployment schedules : {docker_deployment.hash=} {docker_deployment.monitor_schedule_id=} {docker_deployment.metrics_schedule_id=}"
                )
            except RPCError as e:
                print(f"Error deleting previous deployment schedules: {e}")
                # The schedule probably doesn't exist
                pass

    @activity.defn
    async def cleanup_previous_production_deployment(
        self, deployment: SimpleDeploymentDetails
    ):
        docker_deployment = (
            await DockerDeployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service_id
            )
            .select_related("service")
            .afirst()
        )

        if docker_deployment is not None:
            docker_deployment.status = DockerDeployment.DeploymentStatus.REMOVED
            docker_deployment.is_current_production = False
            await docker_deployment.asave()

    @activity.defn
    async def cleanup_previous_unclean_deployments(
        self, deployment: DockerDeploymentDetails
    ) -> List[str]:
        # let's cleanup other deployments if they weren't cleaned up correctly
        previous_deployments = DockerDeployment.objects.filter(
            Q(service_id=deployment.service.id)
            & Q(is_current_production=False)
            & ~Q(hash=deployment.hash)
            & ~Q(status=DockerDeployment.DeploymentStatus.QUEUED)
            & ~Q(status=DockerDeployment.DeploymentStatus.FAILED)
            & ~Q(status=DockerDeployment.DeploymentStatus.REMOVED)
            & ~Q(status=DockerDeployment.DeploymentStatus.CANCELLED)
        ).select_related("service", "service__project")

        deployments: List[DockerDeployment] = []

        async for docker_deployment in previous_deployments:
            print(f"Found uncleaned deployment : {docker_deployment.hash=}")
            swarm_service_name = get_swarm_service_name_for_deployment(
                deployment_hash=docker_deployment.hash,
                project_id=docker_deployment.service.project.id,
                service_id=docker_deployment.service.id,
            )

            try:
                self.docker_client.services.get(swarm_service_name)
            except docker.errors.NotFound:
                # if the service hasn't been cleanup correctly
                deployments.append(docker_deployment)
            else:
                print(
                    f"Found rogue deployment : {docker_deployment.hash=} with service: {swarm_service_name=}"
                )

        jobs: List[Coroutine[Any, Any, None]] = []
        for docker_deployment in deployments:
            jobs.extend(
                [
                    delete_schedule(
                        id=docker_deployment.monitor_schedule_id,
                    ),
                    delete_schedule(
                        id=docker_deployment.metrics_schedule_id,
                    ),
                ]
            )
        try:
            # delete schedules
            await asyncio.gather(*jobs, return_exceptions=True)
        except RPCError:
            # The schedule probably don't exist
            pass

        await previous_deployments.aupdate(
            status=DockerDeployment.DeploymentStatus.REMOVED
        )

        return [dpl.hash for dpl in deployments]

    @activity.defn
    async def create_docker_volumes_for_service(
        self, deployment: DockerDeploymentDetails
    ) -> List[VolumeDto]:
        await deployment_log(
            deployment,
            f"Creating volumes for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        service = deployment.service
        created_volumes: List[VolumeDto] = []
        for volume in service.docker_volumes:
            try:
                self.docker_client.volumes.get(get_volume_resource_name(volume.id))  # type: ignore
            except docker.errors.NotFound:
                created_volumes.append(volume)
                self.docker_client.volumes.create(
                    name=get_volume_resource_name(volume.id),  # type: ignore
                    driver="local",
                    labels=get_resource_labels(service.project_id, parent=service.id),
                )

        await deployment_log(
            deployment,
            f"Volumes created succesfully for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}  ✅",
        )

        return created_volumes

    @activity.defn
    async def create_docker_configs_for_service(
        self, deployment: DockerDeploymentDetails
    ) -> List[ConfigDto]:
        await deployment_log(
            deployment,
            f"Creating configuration files for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        service = deployment.service
        created_configs: List[ConfigDto] = []
        for config in service.configs:
            try:
                self.docker_client.configs.get(
                    get_config_resource_name(config.id, config.version)  # type: ignore
                )
            except docker.errors.NotFound:
                self.docker_client.configs.create(
                    name=get_config_resource_name(config.id, config.version),  # type: ignore
                    labels=get_resource_labels(service.project_id, parent=service.id),
                    data=config.contents.encode("utf-8"),
                )
                created_configs.append(config)

        await deployment_log(
            deployment,
            f"Configuration files created succesfully for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}  ✅",
        )

        return created_configs

    @activity.defn
    async def delete_created_volumes(self, deployment: DeploymentCreateVolumesResult):
        await deployment_log(
            deployment,
            f"Deleting created volumes for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}...",
        )
        for volume in deployment.created_volumes:
            try:
                docker_volume = self.docker_client.volumes.get(
                    get_volume_resource_name(volume.id)  # type: ignore
                )
            except docker.errors.NotFound:
                pass
            else:
                docker_volume.remove(force=True)

        await deployment_log(
            deployment,
            f"Volumes deleted succesfully for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}  ✅",
        )

    @activity.defn
    async def delete_created_configs(self, deployment: DeploymentCreateConfigsResult):
        await deployment_log(
            deployment,
            f"Deleting created config files for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}...",
        )
        for config in deployment.created_configs:
            try:
                docker_config = self.docker_client.configs.get(
                    get_config_resource_name(config.id, config.version)  # type: ignore
                )
            except docker.errors.NotFound:
                pass
            else:
                docker_config.remove()

        await deployment_log(
            deployment,
            f"Config files succesfully deleted for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}  ✅",
        )

    @activity.defn
    async def scale_down_service_deployment(self, deployment: SimpleDeploymentDetails):
        try:
            swarm_service: Service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.project_id,
                    service_id=deployment.service_id,
                )
            )
        except docker.errors.NotFound:
            # do nothing
            # The service for that deployment was removed probably
            return
        else:
            service_labels: dict = swarm_service.attrs["Spec"].get("Labels", {})
            service_labels["status"] = "sleeping"
            update_attributes = dict(
                mode={"Replicated": {"Replicas": 0}}, labels=service_labels
            )

            # This is to fix a bug with exposed ports conflicting with a new deployment, the
            # new deployment creates a service that needs the ports of the service to be available,
            # but it is still used by the old deployment.
            # To fix this we scale down and remove the ports from the old services
            # But only when the `service_snapshot` is provided because that mean we can reconstructs the open ports of the old deployment
            if deployment.service_snapshot is not None:
                update_attributes.update(endpoint_spec=EndpointSpec())

            swarm_service.update(**update_attributes)

            async def wait_for_service_to_be_down():
                print(f"waiting for service `{swarm_service.name=}` to be down...")
                task_list = swarm_service.tasks(filters={"desired-state": "running"})
                while len(task_list) > 0:
                    print(
                        f"service `{swarm_service.name=}` is not down yet, "
                        + f"retrying in `{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}` seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = swarm_service.tasks(
                        filters={"desired-state": "running"}
                    )
                print(f"service `{swarm_service.name=}` is down, YAY !! 🎉")

            await wait_for_service_to_be_down()
            # Change the status to be accurate
            docker_deployment = (
                await DockerDeployment.objects.filter(
                    hash=deployment.hash, service_id=deployment.service_id
                )
                .select_related("service")
                .afirst()
            )

            if docker_deployment is not None:
                try:
                    await asyncio.gather(
                        pause_schedule(
                            id=docker_deployment.monitor_schedule_id,
                            note="Paused to prevent zero-downtime deployment",
                        ),
                        pause_schedule(
                            id=docker_deployment.metrics_schedule_id,
                            note="Paused to prevent zero-downtime deployment",
                        ),
                    )
                    print(f"Paused schedule {docker_deployment.monitor_schedule_id=}")
                except RPCError:
                    print(
                        f"Error pausing schedule {docker_deployment.monitor_schedule_id=}"
                    )
                    # The schedule probably doesn't exist
                    pass
                finally:
                    docker_deployment.status = (
                        DockerDeployment.DeploymentStatus.SLEEPING
                    )
                    await docker_deployment.asave()

    @activity.defn
    async def scale_back_service_deployment(self, deployment: SimpleDeploymentDetails):
        try:
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.project_id,
                    service_id=deployment.service_id,
                )
            )
        except docker.errors.NotFound:
            # do nothing
            # The service for that deployment was removed probably
            return
        else:
            service_labels: dict = swarm_service.attrs["Spec"].get("Labels", {})
            service_labels["status"] = "active"
            update_attributes = dict(
                mode={"Replicated": {"Replicas": 1}}, labels=service_labels
            )

            # If we scaled this deployment by removing the port, we recreate the exposed ports
            if deployment.service_snapshot is not None:
                exposed_ports: dict[int, int] = {}
                new_endpoint_spec = EndpointSpec()

                # We don't expose HTTP ports with docker because they will be handled by caddy directly
                for port in deployment.service_snapshot.ports:
                    exposed_ports[port.host] = port.forwarded
                if len(exposed_ports) > 0:
                    new_endpoint_spec = EndpointSpec(ports=exposed_ports)
                update_attributes.update(endpoint_spec=new_endpoint_spec)

            swarm_service.update(**update_attributes)

            # Change back the status to be accurate
            docker_deployment: DockerDeployment | None = (
                await DockerDeployment.objects.filter(
                    Q(hash=deployment.hash)
                    & Q(service_id=deployment.service_id)
                    & Q(status=DockerDeployment.DeploymentStatus.SLEEPING)
                )
                .select_related("service")
                .afirst()
            )

            if docker_deployment is not None:
                docker_deployment.status = DockerDeployment.DeploymentStatus.STARTING
                await docker_deployment.asave()
                try:
                    await unpause_schedule(
                        id=docker_deployment.monitor_schedule_id,
                        note="Unpaused due to failed healthcheck",
                    )
                except RPCError:
                    # The schedule probably doesn't exist
                    pass

    @activity.defn
    async def pull_image_for_deployment(
        self, deployment: DockerDeploymentDetails
    ) -> bool:
        service = deployment.service
        await deployment_log(
            deployment,
            f"Pulling image {Colors.ORANGE}{service.image}{Colors.ENDC}...",
        )
        try:
            self.docker_client.images.pull(
                repository=service.image,
                auth_config=(
                    service.credentials.to_dict()
                    if service.credentials is not None
                    else None
                ),
            )
        except docker.errors.ImageNotFound:
            await deployment_log(
                deployment,
                f"Error when pulling image {Colors.ORANGE}{service.image}{Colors.ENDC} {Colors.GREY}this image either does not exists for this platform (linux/{platform.machine()}) or may require credentials to pull ❌{Colors.ENDC}",
            )
            return False
        except docker.errors.APIError as e:
            await deployment_log(
                deployment,
                f"Error when pulling image {Colors.ORANGE}{service.image}{Colors.ENDC} {Colors.GREY}{e.explanation} ❌{Colors.ENDC}",
            )
            return False
        else:
            await deployment_log(
                deployment,
                f"Finished pulling image {Colors.ORANGE}{service.image}{Colors.ENDC} ✅",
            )
            return True

    @activity.defn
    async def create_swarm_service_for_docker_deployment(
        self, deployment: DockerDeploymentDetails
    ):
        service = deployment.service

        try:
            self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.service.project_id,
                    service_id=deployment.service.id,
                )
            )
        except docker.errors.NotFound:
            # add environment specific variables
            envs: list[str] = [
                f"{env.key}={env.value}" for env in service.environment.variables
            ]
            env_as_variables = {
                env.key: env.value for env in service.environment.variables
            }

            # then service variables, so that they overwrite the env specific variables
            for env in service.env_variables:
                value = replace_env_variables(env.value, env_as_variables)
                envs.append(f"{env.key}={value}")

            # zane-specific-envs
            envs.extend(
                [
                    "ZANE=true",
                    f"ZANE_ENVIRONMENT={service.environment.name}",
                    f"ZANE_DEPLOYMENT_SLOT={deployment.slot}",
                    f"ZANE_DEPLOYMENT_HASH={deployment.hash}",
                    "ZANE_DEPLOYMENT_TYPE=docker",
                    f"ZANE_PRIVATE_DOMAIN={service.network_alias}",
                    f"ZANE_SERVICE_ID={service.id}",
                    f"ZANE_SERVICE_NAME={service.slug}",
                    f"ZANE_PROJECT_ID={service.project_id}",
                ]
            )

            # Volumes
            mounts: list[str] = []
            docker_volume_list = self.docker_client.volumes.list(
                filters={
                    "label": [
                        f"{key}={value}"
                        for key, value in get_resource_labels(
                            service.project_id, parent=service.id
                        ).items()
                    ]
                }
            )
            access_mode_map = {
                "READ_WRITE": "rw",
                "READ_ONLY": "ro",
            }

            for volume in service.docker_volumes:
                # Only include volumes that will not be deleted
                docker_volume = find_item_in_list(
                    lambda v: v.name == get_volume_resource_name(volume.id),  # type: ignore
                    docker_volume_list,
                )
                if docker_volume is not None:
                    mounts.append(
                        f"{docker_volume.name}:{volume.container_path}:{access_mode_map[volume.mode]}"
                    )
            for volume in service.host_volumes:
                mounts.append(
                    f"{volume.host_path}:{volume.container_path}:{access_mode_map[volume.mode]}"
                )

            # configs
            configs: list[ConfigReference] = []
            docker_config_list = self.docker_client.configs.list(
                filters={
                    "label": [
                        f"{key}={value}"
                        for key, value in get_resource_labels(
                            service.project_id, parent=service.id
                        ).items()
                    ]
                }
            )
            for config in service.configs:
                # Only include configs that will not be deleted
                docker_config = find_item_in_list(
                    lambda v: v.name
                    == get_config_resource_name(config.id, config.version),  # type: ignore
                    docker_config_list,
                )

                if docker_config is not None:
                    configs.append(
                        ConfigReference(
                            config_id=docker_config.id,
                            config_name=docker_config.name,
                            filename=config.mount_path,
                        )
                    )

            # ports
            exposed_ports: dict[int, int] = {}
            endpoint_spec: EndpointSpec | None = None

            # We don't expose HTTP ports with docker because they will be handled by caddy directly
            for port in service.ports:
                exposed_ports[port.host] = port.forwarded

            if len(exposed_ports) > 0:
                endpoint_spec = EndpointSpec(ports=exposed_ports)

            resources: Resources | None = None
            if service.resource_limits is not None:
                nano_cpus = None
                if service.resource_limits.cpus is not None:
                    nano_cpus = int(service.resource_limits.cpus * 1e9)
                mem_limit_in_bytes = None
                if service.resource_limits.memory is not None:
                    mem_limit_in_bytes = convert_value_to_bytes(
                        service.resource_limits.memory.value,
                        service.resource_limits.memory.unit,
                    )
                resources = Resources(
                    cpu_limit=nano_cpus,
                    mem_limit=mem_limit_in_bytes,
                )

            await deployment_log(
                deployment,
                f"Creating service for the deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
            )
            self.docker_client.services.create(
                image=service.image,
                command=service.command,
                name=get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.service.project_id,
                    service_id=deployment.service.id,
                ),
                mounts=mounts,
                endpoint_spec=endpoint_spec,
                env=envs,
                labels=get_resource_labels(
                    service.project_id,
                    deployment_hash=deployment.hash,
                    service=deployment.service.id,
                    status="active",
                ),
                networks=[
                    NetworkAttachmentConfig(
                        target=get_env_network_resource_name(
                            service.environment.id, service.project_id
                        ),
                        aliases=service.network_aliases,
                    ),
                    NetworkAttachmentConfig(
                        target="zane",
                        aliases=[deployment.network_alias],
                    ),
                ],
                update_config=UpdateConfig(
                    order="start-first",
                    parallelism=1,
                ),
                restart_policy=RestartPolicy(
                    condition="any",
                ),
                # this disables the default container healthcheck, since we control the healthcheck externally
                healthcheck=DockerHealthcheckType(test=["NONE"]),
                stop_grace_period=int(30e9),  # stop_grace_period is in nanoseconds
                log_driver="fluentd",
                log_driver_options={
                    "fluentd-address": settings.ZANE_FLUENTD_HOST,
                    "tag": json.dumps(
                        {
                            "service_id": deployment.service.id,
                            "deployment_id": deployment.hash,
                        }
                    ),
                    "mode": "non-blocking",
                    "fluentd-async": "true",
                    "fluentd-max-retries": "10",
                    "fluentd-sub-second-precision": "true",
                },
                resources=resources,
                configs=configs,
            )
            await deployment_log(
                deployment,
                f"Service created succesfully for the deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC} ✅",
            )

    @activity.defn
    async def run_deployment_healthcheck(
        self,
        deployment: DockerDeploymentDetails,
    ) -> tuple[DockerDeployment.DeploymentStatus, str]:
        docker_deployment = (
            await DockerDeployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service.id
            )
            .select_related("service", "service__project", "service__healthcheck")
            .afirst()
        )

        if docker_deployment is None:
            raise ApplicationError(
                "Cannot check a status of a non existent deployment.",
                non_retryable=True,
            )

        swarm_service = self.docker_client.services.get(
            get_swarm_service_name_for_deployment(
                deployment_hash=docker_deployment.hash,
                project_id=docker_deployment.service.project.id,
                service_id=docker_deployment.service.id,
            )
        )

        start_time = monotonic()
        healthcheck = docker_deployment.service.healthcheck

        healthcheck_timeout = (
            healthcheck.timeout_seconds
            if healthcheck is not None
            else settings.DEFAULT_HEALTHCHECK_TIMEOUT
        )
        healthcheck_attempts = 0
        deployment_status, deployment_status_reason = (
            DockerDeployment.DeploymentStatus.UNHEALTHY,
            "The service failed to meet the healthcheck requirements when starting the service.",
        )
        await deployment_log(
            deployment,
            f"Running healthchecks for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        while (monotonic() - start_time) < healthcheck_timeout:
            healthcheck_attempts += 1
            healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)

            await deployment_log(
                deployment,
                f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC}"
                f" | healthcheck_time_left={Colors.ORANGE}{format_seconds(healthcheck_time_left)}{Colors.ENDC} 💓",
            )

            task_list = swarm_service.tasks(
                filters={
                    "label": f"deployment_hash={docker_deployment.hash}",
                    "desired-state": "running",
                }
            )
            if len(task_list) > 0:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                # starting_status = DockerDeployment.DeploymentStatus.STARTING
                # # We set the status to restarting, because we get more than one task for this service when we restart it
                # if len(task_list) > 1:
                #     starting_status = DockerDeployment.DeploymentStatus.RESTARTING

                state_matrix = {
                    DockerSwarmTaskState.NEW: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PENDING: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ASSIGNED: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ACCEPTED: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.READY: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PREPARING: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.STARTING: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.RUNNING: DockerDeployment.DeploymentStatus.HEALTHY,
                    DockerSwarmTaskState.COMPLETE: DockerDeployment.DeploymentStatus.REMOVED,
                    DockerSwarmTaskState.FAILED: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.SHUTDOWN: DockerDeployment.DeploymentStatus.REMOVED,
                    DockerSwarmTaskState.REJECTED: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.ORPHANED: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.REMOVE: DockerDeployment.DeploymentStatus.REMOVED,
                }

                exited_without_error = 0
                deployment_status = state_matrix[most_recent_swarm_task.state]

                all_tasks = swarm_service.tasks(
                    filters={
                        "label": f"deployment_hash={docker_deployment.hash}",
                    }
                )
                if deployment_status == DockerDeployment.DeploymentStatus.STARTING:
                    # We set the status to restarting, because we get more than one task for this service when we restart it
                    if len(all_tasks) > 1:
                        deployment_status = DockerDeployment.DeploymentStatus.RESTARTING

                    docker_deployment.status = deployment_status
                    await docker_deployment.asave()

                deployment_status_reason = (
                    most_recent_swarm_task.Status.Err
                    if most_recent_swarm_task.Status.Err is not None
                    else most_recent_swarm_task.Status.Message
                )

                if most_recent_swarm_task.state == DockerSwarmTaskState.SHUTDOWN:
                    status_code = most_recent_swarm_task.Status.ContainerStatus.ExitCode  # type: ignore
                    if (
                        status_code is not None and status_code != exited_without_error
                    ) or most_recent_swarm_task.Status.Err is not None:
                        deployment_status = DockerDeployment.DeploymentStatus.UNHEALTHY

                if (
                    most_recent_swarm_task.state == DockerSwarmTaskState.RUNNING
                    and most_recent_swarm_task.container_id is not None
                ):
                    if healthcheck is not None:
                        try:
                            print(
                                f"Running custom healthcheck {healthcheck.type=} - {healthcheck.value=}"
                            )
                            if healthcheck.type == HealthCheck.HealthCheckType.COMMAND:
                                container = self.docker_client.containers.get(
                                    most_recent_swarm_task.container_id
                                )
                                exit_code, output = container.exec_run(
                                    cmd=healthcheck.value,
                                    stdout=True,
                                    stderr=True,
                                    stdin=False,
                                )

                                if exit_code == 0:
                                    deployment_status = (
                                        DockerDeployment.DeploymentStatus.HEALTHY
                                    )
                                else:
                                    deployment_status = (
                                        DockerDeployment.DeploymentStatus.UNHEALTHY
                                    )
                                deployment_status_reason = output.decode("utf-8")
                            else:
                                full_url = f"http://{swarm_service.name}:{healthcheck.associated_port}{healthcheck.value}"
                                response = requests.get(
                                    full_url,
                                    timeout=min(healthcheck_time_left, 5),
                                )
                                if status.is_success(response.status_code):
                                    deployment_status = (
                                        DockerDeployment.DeploymentStatus.HEALTHY
                                    )
                                else:
                                    deployment_status = (
                                        DockerDeployment.DeploymentStatus.UNHEALTHY
                                    )
                                deployment_status_reason = response.content.decode(
                                    "utf-8"
                                )
                        except (HTTPError, RequestException) as e:
                            deployment_status = (
                                DockerDeployment.DeploymentStatus.UNHEALTHY
                            )
                            deployment_status_reason = str(e)

                healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)
                if (
                    deployment_status == DockerDeployment.DeploymentStatus.HEALTHY
                    or healthcheck_time_left
                    <= settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL
                ):
                    status_color = (
                        Colors.GREEN
                        if deployment_status
                        == DockerDeployment.DeploymentStatus.HEALTHY
                        else Colors.RED
                    )
                    await deployment_log(
                        deployment,
                        f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                        f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                        f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC}",
                        error=status_color == Colors.RED,
                    )
                    await deployment_log(
                        deployment,
                        f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                        f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                        f"| finished with status {status_color}{deployment_status}{Colors.ENDC}",
                        error=status_color == Colors.RED,
                    )
                    return deployment_status, deployment_status_reason

            await deployment_log(
                deployment,
                f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC}",
                error=True,
            )
            await deployment_log(
                deployment,
                f"Healthcheck for deployment deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                f"| FAILED, Retrying in {Colors.ORANGE}{format_seconds(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)}{Colors.ENDC} 🔄",
                error=True,
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)

        status_color = (
            Colors.GREEN
            if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY
            else Colors.RED
        )
        await deployment_log(
            deployment,
            f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
            f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
            f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC} ✅",
        )
        await deployment_log(
            deployment,
            f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
            f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
            f"| finished with status {status_color}{deployment_status}{Colors.ENDC} ✅",
        )
        return deployment_status, deployment_status_reason

    @activity.defn
    async def expose_docker_deployment_to_http(
        self,
        deployment: DockerDeploymentDetails,
    ):
        # add URL conf for deployment
        service = deployment.service
        if len(service.urls_with_associated_ports) > 0:
            ZaneProxyClient.insert_deployment_urls(deployment)

    @activity.defn
    async def expose_docker_service_to_http(
        self,
        deployment: DockerDeploymentDetails,
    ):
        service = deployment.service
        if len(service.urls) > 0:
            await deployment_log(
                deployment,
                f"Configuring service URLs for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
            )
            previous_deployment: DockerDeployment | None = await (
                DockerDeployment.objects.filter(
                    Q(service_id=deployment.service.id)
                    & Q(queued_at__lt=deployment.queued_at_as_datetime)
                    & ~Q(hash=deployment.hash)
                )
                .order_by("-queued_at")
                .afirst()
            )

            for url in service.urls:
                ZaneProxyClient.upsert_service_url(
                    url=url,
                    current_deployment=deployment,
                    previous_deployment=previous_deployment,
                )

            await deployment_log(
                deployment,
                f"Service URLs for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC} configured successfully ✅",
            )

    @activity.defn
    async def scale_down_and_remove_docker_service_deployment(
        self, deployment: SimpleDeploymentDetails
    ):
        try:
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.project_id,
                    service_id=deployment.service_id,
                )
            )
        except docker.errors.NotFound:
            # Do nothing, The service has already been deleted
            return
        else:
            swarm_service.scale(0)

            async def wait_for_service_to_be_down():
                print(f"waiting for service {swarm_service.name=} to be down...")
                task_list = swarm_service.tasks(filters={"desired-state": "running"})
                while len(task_list) > 0:
                    print(
                        f"service {swarm_service.name=} is not down yet, "
                        + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = swarm_service.tasks(
                        filters={"desired-state": "running"}
                    )
                print(f"service {swarm_service.name=} is down, YAY !! 🎉")

            await wait_for_service_to_be_down()
            swarm_service.remove()

    @activity.defn
    async def remove_old_docker_volumes(self, deployment: DockerDeploymentDetails):
        service = deployment.service
        docker_volume_names = [
            get_volume_resource_name(volume.id)  # type: ignore
            for volume in service.docker_volumes
        ]

        docker_volume_list = self.docker_client.volumes.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service.project_id,
                        parent=service.id,
                    ).items()
                ]
            }
        )

        for volume in docker_volume_list:
            if volume.name not in docker_volume_names:
                volume.remove(force=True)

    @activity.defn
    async def remove_old_docker_configs(self, deployment: DockerDeploymentDetails):
        service = deployment.service
        docker_config_names = [
            get_config_resource_name(config.id, config.version)  # type: ignore
            for config in service.configs
        ]

        docker_config_list = self.docker_client.configs.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service.project_id,
                        parent=service.id,
                    ).items()
                ]
            }
        )

        for config in docker_config_list:
            if config.name not in docker_config_names:
                config.remove()

    @activity.defn
    async def remove_old_urls(self, deployment: DockerDeploymentDetails):
        ZaneProxyClient.cleanup_old_service_urls(deployment)

    @activity.defn
    async def unexpose_docker_service_from_http(
        self, service_details: ArchivedServiceDetails
    ):
        for url in service_details.urls:
            ZaneProxyClient.remove_service_url(service_details.original_id, url)

        for deployment in service_details.deployments:
            for domain in deployment.urls:
                ZaneProxyClient.remove_deployment_url(deployment.hash, domain)

    @activity.defn
    async def unexpose_docker_deployment_from_http(
        self, deployment: DockerDeploymentDetails
    ):
        for url in deployment.urls:
            ZaneProxyClient.remove_deployment_url(deployment.hash, url.domain)

    @activity.defn
    async def remove_changed_urls_in_deployment(
        self, deployment: DockerDeploymentDetails
    ):
        previous_deployment: DockerDeployment | None = await (
            DockerDeployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(queued_at__lt=deployment.queued_at_as_datetime)
                & ~Q(hash=deployment.hash)
            )
            .order_by("-queued_at")
            .afirst()
        )
        new_urls = [
            URLDto.from_dict(change.new_value)
            for change in deployment.changes
            if change.type == DockerDeploymentChange.ChangeType.ADD
            and change.field == DockerDeploymentChange.ChangeField.URLS
        ]
        updated_url_changes = [
            change
            for change in deployment.changes
            if change.type == DockerDeploymentChange.ChangeType.UPDATE
            and change.field == DockerDeploymentChange.ChangeField.URLS
        ]
        for url in new_urls:
            ZaneProxyClient.remove_service_url(deployment.service.id, url)

        for url_change in updated_url_changes:
            old_url = URLDto.from_dict(url_change.old_value)
            new_url = URLDto.from_dict(url_change.new_value)

            # Readd old url
            ZaneProxyClient.upsert_service_url(
                url=old_url,
                current_deployment=deployment,
                previous_deployment=previous_deployment,
            )

            # This is so that we don't delete the urls we just added
            # Sometimes the change can just be about `strip_prefix` and it might delete the old URL
            if (
                new_url.domain != old_url.domain
                or new_url.base_path != old_url.base_path
            ):
                ZaneProxyClient.remove_service_url(deployment.service.id, new_url)

    @activity.defn
    async def create_deployment_stats_schedule(
        self, deployment: DockerDeploymentDetails
    ):
        try:
            docker_deployment = (
                await DockerDeployment.objects.filter(hash=deployment.hash)
                .select_related("service")
                .afirst()
            )

            if docker_deployment is None:
                raise DockerDeployment.DoesNotExist(
                    f"Docker deployment with hash='{deployment.hash}' does not exist."
                )
        except DockerDeployment.DoesNotExist:
            raise ApplicationError(
                "Cannot create a stats schedule for a non existent deployment.",
                non_retryable=True,
            )
        else:
            details = SimpleDeploymentDetails(
                hash=deployment.hash,
                service_id=deployment.service.id,
                project_id=deployment.service.project_id,
            )
            await create_schedule(
                workflow=GetDockerDeploymentStatsWorkflow.run,
                args=details,
                id=docker_deployment.metrics_schedule_id,
                interval=timedelta(seconds=30),
                task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
            )

    @activity.defn
    async def create_deployment_healthcheck_schedule(
        self, deployment: DockerDeploymentDetails
    ):
        try:
            docker_deployment = (
                await DockerDeployment.objects.filter(hash=deployment.hash)
                .select_related("service", "service__healthcheck")
                .afirst()
            )

            if docker_deployment is None:
                raise DockerDeployment.DoesNotExist(
                    f"Docker deployment with hash='{deployment.hash}' does not exist."
                )
        except DockerDeployment.DoesNotExist:
            raise ApplicationError(
                "Cannot create a healthcheck schedule for a non existent deployment.",
                non_retryable=True,
            )
        else:
            healthcheck: Optional[HealthCheck] = docker_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=deployment.hash,
                    service_id=deployment.service.id,
                    project_id=deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                            associated_port=healthcheck.associated_port,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )

            interval_seconds = (
                healthcheck_details.healthcheck.interval_seconds
                if healthcheck_details.healthcheck is not None
                else settings.DEFAULT_HEALTHCHECK_INTERVAL
            )

            await create_schedule(
                workflow=MonitorDockerDeploymentWorkflow.run,
                args=healthcheck_details,
                id=docker_deployment.monitor_schedule_id,
                interval=timedelta(seconds=interval_seconds),
                task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
            )
