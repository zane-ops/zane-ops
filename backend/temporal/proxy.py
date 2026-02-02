import asyncio

from typing import Dict, List, TypedDict

from .shared import DeploymentDetails, DeploymentURLDto, ProxyURLRoute
from zane_api.models import Deployment, URL
from zane_api.utils import strip_slash_if_exists, find_item_in_sequence
from django.conf import settings
from zane_api.dtos import URLDto
import requests
from rest_framework import status

from compose.dtos import ComposeStackUrlRouteDto
from .helpers import get_swarm_service_name_for_deployment


class ZaneProxyEtagError(Exception):
    pass


class ZaneProxyClient:
    MAX_ETAG_ATTEMPTS = 3

    class ServiceType:
        MANAGED_SERVICE = "managed_service"
        COMPOSE_STACK_SERVICE = "compose_stack_service"
        BUILD_REGISTRY = "build_registry"

        @classmethod
        def choices(cls) -> List[str]:
            return [cls.MANAGED_SERVICE, cls.COMPOSE_STACK_SERVICE, cls.BUILD_REGISTRY]

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
                "key": "zane_service_type",
                "value": ZaneProxyClient.ServiceType.MANAGED_SERVICE,
            },
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
                "value": ZaneProxyClient.ServiceType.BUILD_REGISTRY,
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
        all_urls: Dict[str, List[ComposeStackUrlRouteDto]],
    ) -> List[tuple[str, str, str]]:
        response = requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes", timeout=5
        )

        service_url_routes = [
            cls._get_id_for_compose_stack_service_url(
                stack_id=stack_id,
                url=url,
                service_name=service,
            )
            for service, urls in all_urls.items()
            for url in urls
        ]
        delete_url_routes: List[tuple[str, str, str]] = []

        for route in response.json():
            if route["@id"].startswith(stack_id):
                host = route["match"][0]["host"][0]
                path = route["match"][0]["path"][0]

                if route["@id"] not in service_url_routes:
                    delete_url_routes.append((route["@id"], host, path))

        await asyncio.gather(
            *[
                cls._delete_route(route_id)
                for route_id, _host, _path in delete_url_routes
            ]
        )
        return delete_url_routes

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
                "value": ZaneProxyClient.ServiceType.COMPOSE_STACK_SERVICE,
            },
            {
                "handler": "log_append",
                "key": "zane_stack_service_name",
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
    ) -> str:
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
            return cls._get_id_for_compose_stack_service_url(
                stack_id=stack_id,
                service_name=service_name,
                url=url,
            )

        raise ZaneProxyEtagError(
            f"Failed inserting the url {url} in the proxy because `Etag` precondition failed"
        )
