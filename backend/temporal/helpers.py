import asyncio
import os
import shutil

from typing import Any, Coroutine, Dict, List, Literal, TypedDict, cast
from docker.models.services import Service as DockerService


from .shared import DeploymentDetails, DeploymentURLDto, ProxyURLRoute
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
from zane_api.utils import replace_placeholders, DockerSwarmTask, DockerSwarmTaskState
import requests
from rest_framework import status
from enum import Enum, auto
from .constants import (
    SERVER_RESOURCE_LIMIT_COMMAND,
    CADDYFILE_BASE_STATIC,
    CADDYFILE_CUSTOM_INDEX_PAGE,
    CADDYFILE_CUSTOM_NOT_FOUND_PAGE,
    SERVICE_DETECTED_PORTS_CACHE_KEY,
)
from typing import Protocol, runtime_checkable
from datetime import timedelta
from compose.dtos import (
    ComposeStackUrlRouteDto,
    ComposeStackServiceStatus,
    ComposeStackSnapshot,
)


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
        print(f"check_if_docker_image_exists({image=}, {credentials=})")
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
class StackLike(Protocol):
    @property
    def id(self) -> str: ...


@runtime_checkable
class StackDeploymentLike(Protocol):
    @property
    def hash(self) -> str: ...

    @property
    def stack(self) -> StackLike: ...


@runtime_checkable
class StackServiceLike(Protocol):
    @property
    def stack_id(self) -> str: ...

    @property
    def service_id(self) -> str: ...


@runtime_checkable
class DeploymentResultLike(Protocol):
    @property
    def deployment_hash(self) -> str: ...

    @property
    def service_id(self) -> str: ...


async def deployment_log(
    deployment: DeploymentLike
    | DeploymentResultLike
    | StackDeploymentLike
    | StackServiceLike,
    message: str | List[str],
    source: Literal["SYSTEM", "SERVICE", "BUILD"] = RuntimeLogSource.SYSTEM,
    error=False,
):
    stack_id = None
    deployment_id = None
    service_id = None
    match deployment:
        case DeploymentLike():
            deployment_id = deployment.hash
            service_id = deployment.service.id
        case DeploymentResultLike():
            deployment_id = deployment.deployment_hash
            service_id = deployment.service_id
        case StackDeploymentLike():
            deployment_id = deployment.hash
            stack_id = deployment.stack.id
        case StackServiceLike():
            stack_id = deployment.stack_id
            service_id = deployment.service_id
        case _:
            raise TypeError(
                f"type {type(deployment)} doesn't match one of {[DeploymentLike, DeploymentResultLike, StackDeploymentLike, StackServiceLike]}"
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
                stack_id=stack_id,
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
                    "path": [cls._normalize_base_path(url.base_path)],
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
            f"Failed inserting the url {url} in the proxy because `Etag` precondition failed"
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

    @classmethod
    def get_uri_for_build_registry(cls, registry_alias: str):
        return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{registry_alias}"

    @classmethod
    def _get_request_for_build_registry(
        cls, registry_id: str, registry_alias: str, domain: str, is_secure: bool
    ):
        reverse_proxy_handler = {
            "flush_interval": -1,
            "handler": "reverse_proxy",
            "upstreams": [{"dial": f"{registry_alias}:5000"}],
        }

        if is_secure:
            reverse_proxy_handler["headers"] = {
                "request": {
                    "set": {
                        "X-Forwarded-Proto": ["https"],
                    }
                }
            }

        proxy_handlers = [
            {
                "handler": "log_append",
                "key": "zane_registry_id",
                "value": registry_id,
            },
            {
                "handler": "log_append",
                "key": "zane_service_type",
                "value": "BUILD_REGISTRY",
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
                    },
                },
            },
            {
                "handler": "encode",
                "encodings": {"gzip": {}},
                "prefer": ["gzip"],
            },
            reverse_proxy_handler,
        ]

        return {
            "@id": registry_alias,
            "match": [{"host": [domain]}],
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [{"handle": proxy_handlers}],
                }
            ],
        }

    @classmethod
    def upsert_registry_url(
        cls, registry_id: str, registry_alias: str, domain: str, is_secure: bool
    ) -> bool:
        existing_response = requests.get(
            cls.get_uri_for_build_registry(registry_alias), timeout=5
        )
        existing = False
        if existing_response.status_code == status.HTTP_200_OK:
            existing = True

        attempts = 0

        while attempts < cls.MAX_ETAG_ATTEMPTS:
            attempts += 1

            new_url = cls._get_request_for_build_registry(
                registry_id, registry_alias, domain, is_secure
            )
            # now we create or modify the config for the URL
            if existing:
                etag = existing_response.headers.get("etag")
                response = requests.patch(
                    cls.get_uri_for_build_registry(registry_alias),
                    headers={"content-type": "application/json", "If-Match": etag},
                    json=new_url,
                    timeout=5,
                )
            else:
                response = requests.get(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes",
                    timeout=5,
                )
                etag = response.headers.get("etag")

                routes: list[dict[str, dict]] = [
                    route for route in response.json() if route["@id"] != registry_alias
                ]

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
            f"Failed inserting the url `{domain}` in the proxy because `Etag` precondition failed"
        )

    @classmethod
    def remove_build_registry_url(cls, registry_alias: str):
        requests.delete(
            cls.get_uri_for_build_registry(registry_alias),
            timeout=5,
        )

    @classmethod
    def _get_id_for_compose_stack_service_url(
        cls,
        stack_id: str,
        service_name: str,
        url: ComposeStackUrlRouteDto,
    ):
        normalized_path = strip_slash_if_exists(
            url.base_path, strip_end=True, strip_start=True
        ).replace("/", "-")

        if len(normalized_path) == 0:
            normalized_path = "*"
        return f"{stack_id}-{service_name}-{url.domain}-{normalized_path}"

    @classmethod
    def get_uri_for_compose_stack_service(
        cls,
        stack_id: str,
        service_name: str,
        url: ComposeStackUrlRouteDto,
    ):
        return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{cls._get_id_for_compose_stack_service_url(stack_id, service_name, url)}"

    @staticmethod
    async def _delete_route(route_id: str):
        requests.delete(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{route_id}",
            timeout=5,
        )

    @classmethod
    async def delete_all_stack_urls(
        cls,
        stack_id: str,
    ) -> List[ProxyURLRoute]:
        response = requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes", timeout=5
        )
        await asyncio.gather(
            *[
                cls._delete_route(route["@id"])
                for route in response.json()
                if route["@id"].startswith(stack_id)
            ]
        )
        return [
            ProxyURLRoute(
                domain=route["match"][0]["host"][0],
                base_path=route["match"][0]["path"][0],
            )
            for route in response.json()
            if route["@id"].startswith(stack_id)
        ]

    @staticmethod
    def _normalize_base_path(base_path: str):
        if base_path == "/":
            return "/*"
        return f"{strip_slash_if_exists(base_path, strip_end=True, strip_start=False)}*"

    @classmethod
    async def cleanup_old_compose_stack_service_urls(
        cls,
        stack_id: str,
        all_urls: List[ComposeStackUrlRouteDto],
    ):
        response = requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes", timeout=5
        )
        service_url_routes = [
            (
                url.domain,
                cls._normalize_base_path(url.base_path),
            )
            for url in all_urls
        ]

        route_delete_requests: List[Coroutine[Any, Any, None]] = []
        for route in response.json():
            if route["@id"].startswith(stack_id):
                route_pair = (
                    route["match"][0]["host"][0],
                    route["match"][0]["path"][0],
                )
                if route_pair not in service_url_routes:
                    route_delete_requests.append(cls._delete_route(route["@id"]))

        await asyncio.gather(*route_delete_requests)

    @classmethod
    def _get_request_for_compose_stack_service_url(
        cls,
        stack_id: str,
        stack_hash_prefix: str,
        service_name: str,
        url: ComposeStackUrlRouteDto,
    ):
        proxy_handlers = [
            {
                "handler": "log_append",
                "key": "zane_service_type",
                "value": "compose_stack_service",
            },
            {
                "handler": "log_append",
                "key": "zane_service_name",
                "value": service_name,
            },
            {
                "handler": "log_append",
                "key": "zane_stack_id",
                "value": stack_id,
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
                    },
                },
                "request": {
                    "add": {
                        "x-request-id": ["{http.request.uuid}"],
                    },
                },
            },
            {
                "handler": "encode",
                "encodings": {"gzip": {}},
                "prefer": ["gzip"],
            },
        ]

        if url.strip_prefix:
            proxy_handlers.append(
                {
                    "handler": "rewrite",
                    "strip_path_prefix": strip_slash_if_exists(
                        url.base_path,
                        strip_end=True,
                        strip_start=False,
                    ),
                }
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
                    {
                        "dial": f"{stack_hash_prefix}_{service_name}.{settings.ZANE_INTERNAL_DOMAIN}:{url.port}"
                    },
                ],
            }
        )

        return {
            "@id": cls._get_id_for_compose_stack_service_url(
                stack_id,
                service_name,
                url,
            ),
            "match": [
                {
                    "path": [cls._normalize_base_path(url.base_path)],
                    "host": [url.domain],
                }
            ],
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [{"handle": proxy_handlers}],
                }
            ],
        }

    @classmethod
    def upsert_compose_stack_service_url(
        cls,
        stack_id: str,
        stack_hash_prefix: str,
        service_name: str,
        url: ComposeStackUrlRouteDto,
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
                != cls._get_id_for_compose_stack_service_url(
                    stack_id=stack_id,
                    service_name=service_name,
                    url=url,
                )
            ]
            new_url = cls._get_request_for_compose_stack_service_url(
                stack_id=stack_id,
                service_name=service_name,
                stack_hash_prefix=stack_hash_prefix,
                url=url,
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
            f"Failed inserting the url {url} in the proxy because `Etag` precondition failed"
        )


class GitDeploymentStep(Enum):
    INITIALIZED = auto()
    CLONING_REPOSITORY = auto()
    REPOSITORY_CLONED = auto()
    BUILDING_IMAGE = auto()
    IMAGE_BUILT = auto()
    PUSHING_IMAGE = auto()
    IMAGE_PUSHED = auto()
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
            dict(page={"index": options.index_page or "./index.html"}),
        )
    elif options.not_found_page is not None:
        custom_replacers["not_found"] = replace_placeholders(
            CADDYFILE_CUSTOM_NOT_FOUND_PAGE,
            dict(
                page={"not_found": options.not_found_page},
            ),
        )

    return replace_placeholders(base, dict(custom=custom_replacers))


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
                env.value, dict(env=parent_environment_variables)
            )
            for env in service.env_variables
        }
    )
    build_envs.update(
        {
            env.key: replace_placeholders(
                env.value,
                dict(
                    deployment={
                        "slot": deployment.slot,
                        "hash": deployment.hash,
                    }
                ),
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


def get_service_open_port_key(deployment_id: str):
    return f"{SERVICE_DETECTED_PORTS_CACHE_KEY}_{deployment_id}"


OBFUSCATED_VALUE = "**********"
# Keys that should not be obfuscated in logs
NON_SECRET_BUILD_ARGS = {
    "BUILDKIT_SYNTAX",
    "secrets-hash",
    "cache-key",
    "FORCE_COLOR",
    "ZANE",
}
# Prefixes for env keys that should not be obfuscated
NON_SECRET_ENV_PREFIXES = ("ZANE_", "NIXPACKS_", "RAILPACK_")


def _should_obfuscate_key(key: str) -> bool:
    if key in NON_SECRET_BUILD_ARGS:
        return False
    if key.startswith(NON_SECRET_ENV_PREFIXES):
        return False
    return True


def obfuscate_env_in_command(
    cmd_args: list[str], env_flags: list[str] = ["--build-arg", "--env", "--secret"]
) -> str:
    """
    Returns the command as a string with env values obfuscated for logging.
    Detects patterns like: --build-arg KEY=value, --env KEY=value, --secret id=KEY,env=KEY
    """
    import shlex

    result = []
    i = 0
    while i < len(cmd_args):
        arg = cmd_args[i]
        if arg in env_flags and i + 1 < len(cmd_args):
            next_arg = cmd_args[i + 1]
            if "=" in next_arg:
                # Handle --secret id=KEY,env=KEY (don't obfuscate, no value exposed)
                if arg == "--secret":
                    result.append(arg)
                    result.append(next_arg)
                else:
                    # Handle --build-arg KEY=value or --env KEY=value
                    key = next_arg.split("=", 1)[0]
                    if _should_obfuscate_key(key):
                        result.append(arg)
                        result.append(f"{key}={OBFUSCATED_VALUE}")
                    else:
                        result.append(arg)
                        result.append(next_arg)
            else:
                result.append(arg)
                result.append(shlex.quote(next_arg))
            i += 2
        else:
            result.append(shlex.quote(arg) if " " in arg else arg)
            i += 1
    return " ".join(result)


def obfuscate_env_in_shell_command(cmd: str, build_envs: dict[str, str]) -> str:
    """
    Returns a copy of the shell command with env values obfuscated for logging.
    Replaces KEY='value' or KEY=value prefixes with KEY=**********
    """
    import re

    result = cmd
    for key in build_envs:
        if not _should_obfuscate_key(key):
            continue
        # Match KEY='...' or KEY="..." or KEY=unquoted patterns
        pattern = rf"(\s|^){re.escape(key)}=(\'[^\']*\'|\"[^\"]*\"|\S+)"
        result = re.sub(pattern, rf"\1{key}={OBFUSCATED_VALUE}", result)
    return result


async def get_compose_stack_swarm_service_status(
    service: DockerService, stack: ComposeStackSnapshot
) -> Dict[str, Any]:
    service_mode = service.attrs["Spec"]["Mode"]
    # Mode is a dict in the format:
    # {
    #   "Mode": {
    #     "Replicated": {
    #       "Replicas": 0
    #     },
    #     "Global": {},
    #     "ReplicatedJob": {
    #       "MaxConcurrent": 1,
    #       "TotalCompletions": 0
    #     },
    #     "GlobalJob": {}
    #   }
    # }

    service_status = service.attrs["ServiceStatus"]
    # ServiceStatus is a dict in the format:
    # {
    #   "RunningTasks": 1,
    #   "DesiredTasks": 1,
    #   "CompletedTasks": 0
    # }

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

    # Get counts from ServiceStatus
    running_replicas = service_status["RunningTasks"]
    desired_replicas = service_status["DesiredTasks"]
    completed_replicas = service_status.get("CompletedTasks", 0)

    # Get all tasks for the tasks list
    tasks = [DockerSwarmTask.from_dict(task) for task in service.tasks()]

    # Determine status based on mode
    is_job = mode_type in ["replicated-job", "global-job"]

    if is_job:
        # For jobs, healthy means completed >= desired
        status = (
            ComposeStackServiceStatus.HEALTHY
            if completed_replicas >= desired_replicas
            else ComposeStackServiceStatus.STARTING
        )
    else:
        # For regular services, healthy means running >= desired
        if running_replicas == desired_replicas == 0:
            status = ComposeStackServiceStatus.SLEEPING
        elif running_replicas >= desired_replicas:
            status = ComposeStackServiceStatus.HEALTHY
        else:
            # Check if any tasks are in failed states
            unhealthy_states = [
                DockerSwarmTaskState.FAILED,
                DockerSwarmTaskState.REJECTED,
                DockerSwarmTaskState.ORPHANED,
            ]

            has_failed_tasks = any(t.state in unhealthy_states for t in tasks)

            # Check for shutdown tasks with non-zero exit codes
            has_errored_shutdown = any(
                t.state == DockerSwarmTaskState.SHUTDOWN
                and (t.exit_code is not None and t.exit_code != 0)
                for t in tasks
            )

            if has_failed_tasks or has_errored_shutdown:
                status = ComposeStackServiceStatus.UNHEALTHY
            else:
                status = ComposeStackServiceStatus.STARTING

    service_name = (
        cast(str, service.name)
        .removeprefix(f"{stack.name}_")
        .removeprefix(f"{stack.hash_prefix}_")
    )

    # Get image from service spec
    image = service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
    # Remove the digest suffix if present (e.g., "nginx:latest@sha256:...")
    if "@" in image:
        image = image.split("@")[0]

    return {
        "name": service_name,
        "image": image,
        "mode": mode_type,
        "status": status,
        "desired_replicas": desired_replicas,
        "running_replicas": running_replicas,
        "updated_at": timezone.now().isoformat(),
        "tasks": [
            {
                "status": task.state.value,
                "image": task.image,
                "message": task.message,
                "exit_code": task.exit_code,
            }
            for task in tasks
        ],
    }
