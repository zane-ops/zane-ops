import os
import shutil

from typing import Any, Dict, List, Literal, TypedDict
from .shared import (
    DeploymentDetails,
    DeploymentURLDto,
)
from zane_api.models import (
    Deployment,
    URL,
)
from zane_api.utils import (
    strip_slash_if_exists,
    find_item_in_sequence,
    cache_result,
    excerpt,
    escape_ansi,
)
from search.loki_client import LokiSearchClient
from search.dtos import RuntimeLogDto, RuntimeLogLevel, RuntimeLogSource
from django.conf import settings
from django.utils import timezone
import docker
import docker.errors
from docker.models.services import Service
from zane_api.dtos import (
    URLDto,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
)
from zane_api.utils import replace_placeholders
import requests
from rest_framework import status
from enum import Enum, auto
from .constants import (
    SERVER_RESOURCE_LIMIT_COMMAND,
    CADDYFILE_BASE_STATIC,
    CADDYFILE_CUSTOM_INDEX_PAGE,
    CADDYFILE_CUSTOM_NOT_FOUND_PAGE,
)
from typing import Protocol, runtime_checkable
from datetime import timedelta

docker_client: docker.DockerClient | None = None


def get_docker_client():
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


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


def get_buildkit_builder_resource_name(env_id: str):
    return f"builder-zane-{env_id.lower().replace('_', '-')}"


def get_swarm_service_name_for_deployment(
    deployment_hash: str,
    project_id: str,
    service_id: str,
):
    return f"srv-{project_id}-{service_id}-{deployment_hash}"


@cache_result(timeout=timedelta(hours=1))
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


class ServiceLike(Protocol):
    @property
    def id(self) -> str: ...


@runtime_checkable
class DeploymentLike(Protocol):
    @property
    def hash(self) -> str: ...

    @property
    def service(self) -> ServiceLike: ...


@runtime_checkable
class DeploymentResultLike(Protocol):
    @property
    def deployment_hash(self) -> str: ...

    @property
    def service_id(self) -> str: ...


async def deployment_log(
    deployment: DeploymentLike | DeploymentResultLike,
    message: str | List[str],
    source: Literal["SYSTEM", "SERVICE", "BUILD"] = RuntimeLogSource.SYSTEM,
    error=False,
):
    match deployment:
        case DeploymentLike():
            deployment_id = deployment.hash
            service_id = deployment.service.id
        case DeploymentResultLike():
            deployment_id = deployment.deployment_hash
            service_id = deployment.service_id
        case _:
            raise TypeError(
                f"type {type(deployment)} doesn't match {DeploymentLike} or {DeploymentResultLike}"
            )
    search_client = LokiSearchClient(host=settings.LOKI_HOST)

    MAX_COLORED_CHARS = 1000
    messages = []
    if isinstance(message, list):
        messages = message
    else:
        messages = [message]

    logs = []
    for msg in messages:
        current_time = timezone.now()
        print(f"[{current_time.isoformat()}]: {msg}")
        logs.append(
            RuntimeLogDto(
                source=source,
                level=RuntimeLogLevel.INFO if not error else RuntimeLogLevel.ERROR,
                content=excerpt(msg, MAX_COLORED_CHARS),
                content_text=excerpt(escape_ansi(msg), MAX_COLORED_CHARS),
                time=current_time,
                created_at=current_time,
                deployment_id=deployment_id,
                service_id=service_id,
            )
        )

    search_client.bulk_insert(
        docs=logs,
    )


class ZaneProxyEtagError(Exception):
    pass


class ZaneProxyClient:
    MAX_ETAG_ATTEMPTS = 3

    @classmethod
    def _get_id_for_deployment(cls, deployment_hash: str, domain: str):
        return f"{deployment_hash}-{domain}"

    @classmethod
    def get_uri_for_deployment(cls, deployment_hash: str, domain: str):
        return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{cls._get_id_for_deployment(deployment_hash, domain)}"

    @classmethod
    def _get_request_for_deployment_url(
        cls, deployment: DeploymentDetails, url: DeploymentURLDto
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
        current_deployment: DeploymentDetails | Deployment,
        previous_deployment: Deployment | DeploymentDetails | None,
    ):
        AuthDict = TypedDict("AuthDict", {"username": str, "password": str})
        auth_options: AuthDict | None = None
        match current_deployment:
            case DeploymentDetails():
                environment = current_deployment.service.environment
                if environment.is_preview and environment.preview_metadata is not None:
                    preview_meta = environment.preview_metadata
                    if (
                        preview_meta.auth_enabled
                        and preview_meta.auth_user
                        and preview_meta.auth_password
                    ):
                        auth_options = {
                            "username": preview_meta.auth_user,
                            "password": preview_meta.auth_password,
                        }
            case Deployment():
                preview_meta = current_deployment.service.environment.preview_metadata
                if (
                    preview_meta is not None
                    and preview_meta.auth_enabled
                    and preview_meta.auth_user
                    and preview_meta.auth_password
                ):
                    auth_options = {
                        "username": preview_meta.auth_user,
                        "password": preview_meta.auth_password,
                    }

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
                "key": "zane_deployment_id",
                "value": current_deployment.hash,
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

        if auth_options is not None:
            import bcrypt

            proxy_handlers.append(
                {
                    "handler": "authentication",
                    "providers": {
                        "http_basic": {
                            "accounts": [
                                {
                                    "password": bcrypt.hashpw(
                                        auth_options["password"].encode("utf-8"),
                                        bcrypt.gensalt(),
                                    ).decode("utf-8"),
                                    "username": auth_options["username"],
                                }
                            ],
                            "hash": {"algorithm": "bcrypt"},
                            "hash_cache": {},
                        }
                    },
                },
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

            # Add final reverse proxy mapping
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
    def insert_deployment_urls(cls, deployment: DeploymentDetails):
        for url in deployment.urls:
            response = requests.get(
                cls.get_uri_for_deployment(deployment.hash, url.domain),
                timeout=5,
            )

            # if the domain doesn't exist we create the config for the domain
            if response.status_code == status.HTTP_404_NOT_FOUND:
                deployment_url = find_item_in_sequence(
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
        current_deployment: DeploymentDetails | Deployment,
        previous_deployment: Deployment | DeploymentDetails | None,
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
                url=url,
                current_deployment=current_deployment,
                previous_deployment=previous_deployment,
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
    def cleanup_old_service_urls(cls, deployment: DeploymentDetails):
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


class GitDeploymentStep(Enum):
    INITIALIZED = auto()
    CLONING_REPOSITORY = auto()
    REPOSITORY_CLONED = auto()
    BUILDING_IMAGE = auto()
    IMAGE_BUILT = auto()
    VOLUMES_CREATED = auto()
    CONFIGS_CREATED = auto()
    PREVIOUS_DEPLOYMENT_SCALED_DOWN = auto()
    SWARM_SERVICE_CREATED = auto()
    DEPLOYMENT_EXPOSED_TO_HTTP = auto()
    SERVICE_EXPOSED_TO_HTTP = auto()
    FINISHED = auto()

    def __lt__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value >= other.value
        return NotImplemented


class DockerDeploymentStep(Enum):
    INITIALIZED = auto()
    VOLUMES_CREATED = auto()
    CONFIGS_CREATED = auto()
    PREVIOUS_DEPLOYMENT_SCALED_DOWN = auto()
    SWARM_SERVICE_CREATED = auto()
    DEPLOYMENT_EXPOSED_TO_HTTP = auto()
    SERVICE_EXPOSED_TO_HTTP = auto()
    FINISHED = auto()

    def __lt__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value >= other.value
        return NotImplemented


def generate_caddyfile_for_static_website(
    options: StaticDirectoryBuilderOptions | NixpacksBuilderOptions,
):
    base = CADDYFILE_BASE_STATIC
    custom_replacers = {
        "index": "",
        "not_found": "",
    }
    if options.is_spa:
        custom_replacers["index"] = replace_placeholders(
            CADDYFILE_CUSTOM_INDEX_PAGE,
            {"index": options.index_page or "./index.html"},
            placeholder="page",
        )
    elif options.not_found_page is not None:
        custom_replacers["not_found"] = replace_placeholders(
            CADDYFILE_CUSTOM_NOT_FOUND_PAGE,
            {"not_found": options.not_found_page},
            placeholder="page",
        )

    return replace_placeholders(base, custom_replacers, placeholder="custom")


def get_build_environment_variables_for_deployment(
    deployment: DeploymentDetails,
) -> dict[str, str]:
    service = deployment.service
    # pass all env variables
    parent_environment_variables = {
        env.key: env.value for env in service.environment.variables
    }

    build_envs: dict[str, str] = {**parent_environment_variables}
    build_envs.update(
        {
            env.key: replace_placeholders(
                env.value, parent_environment_variables, "env"
            )
            for env in service.env_variables
        }
    )
    build_envs.update(
        {
            env.key: replace_placeholders(
                env.value,
                {
                    "slot": deployment.slot,
                    "hash": deployment.hash,
                },
                "deployment",
            )
            for env in service.system_env_variables
        }
    )
    return build_envs


def get_swarm_service_aliases_ips_on_network(
    services: List[str], network_name: str
) -> Dict[str, str]:
    """
    Retrieve the IP addresses for a list of service aliases on a given Docker network.

    :param services: List of service names (as strings) to inspect.
    :param network_name: Name of the Docker network to query.
    :return: A dict mapping each network alias (str) to its IP address (str).
    """
    client = docker.from_env()
    # get target network ID
    network = client.networks.get(network_name)
    network_id = network.id

    alias_ip_map: Dict[str, str] = {}

    # list only the services we care about
    swarm_services: List[Service] = client.services.list(filters={"name": services})
    for svc in swarm_services:
        # find the VIP for this service on the target network
        vip = next(
            (
                vip_entry["Addr"].split("/")[0]
                for vip_entry in svc.attrs.get("Endpoint", {}).get("VirtualIPs", [])
                if vip_entry["NetworkID"] == network_id
            ),
            None,
        )
        if vip is None:
            continue

        # record each alias on that network
        for net in svc.attrs["Spec"]["TaskTemplate"].get("Networks", []):
            if net.get("Target") != network_id:
                continue
            for alias in net.get("Aliases", []):
                alias_ip_map[alias] = vip

    return alias_ip_map


def empty_folder(folder_path: str):
    for file_object in os.listdir(folder_path):
        file_object_path = os.path.join(folder_path, file_object)
        if os.path.isfile(file_object_path) or os.path.islink(file_object_path):
            os.unlink(file_object_path)
        else:
            shutil.rmtree(file_object_path, ignore_errors=True)
