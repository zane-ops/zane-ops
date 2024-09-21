import asyncio
import json
from datetime import timedelta
from typing import List, Optional, TypedDict

from rest_framework import status
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError

from .main import create_schedule, delete_schedule, pause_schedule, unpause_schedule

with workflow.unsafe.imports_passed_through():
    from .schedules import MonitorDockerDeploymentWorkflow
    from django import db
    import docker
    import docker.errors
    from ..models import (
        Project,
        ArchivedProject,
        ArchivedDockerService,
        DockerDeployment,
        HealthCheck,
        URL,
        DockerDeploymentChange,
        SimpleLog,
    )
    from docker.models.networks import Network
    from urllib3.exceptions import HTTPError
    from requests import RequestException
    import requests
    from docker.types import (
        EndpointSpec,
        NetworkAttachmentConfig,
        RestartPolicy,
        Resources,
    )
    from django.conf import settings
    from django.utils import timezone
    from time import monotonic
    from django.db.models import Q, QuerySet
    from ..utils import (
        strip_slash_if_exists,
        find_item_in_list,
        format_seconds,
        DockerSwarmTask,
        DockerSwarmTaskState,
        Colors,
        cache_result,
        convert_value_to_bytes,
    )

from ..dtos import (
    URLDto,
    HealthCheckDto,
    VolumeDto,
)
from .shared import (
    ProjectDetails,
    ArchivedProjectDetails,
    ArchivedServiceDetails,
    SimpleDeploymentDetails,
    DockerDeploymentDetails,
    DeploymentHealthcheckResult,
    HealthcheckDeploymentDetails,
    DeploymentCreateVolumesResult,
)

docker_client: docker.DockerClient | None = None
SERVER_RESOURCE_LIMIT_COMMAND = (
    "sh -c 'nproc && grep MemTotal /proc/meminfo | awk \"{print \\$2 * 1024}\"'"
)
ONE_HOUR = 3600  # seconds


def get_docker_client():
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


class DockerAuthConfig(TypedDict):
    username: str
    password: str


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
    image: str, credentials: DockerAuthConfig = None
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
            dict(
                full_image=image["name"],
                description=image["description"],
            )
        )
    return images_to_return


def get_network_resource_name(project_id: str) -> str:
    return f"net-{project_id}"


def get_resource_labels(project_id: str, **kwargs):
    return {"zane-managed": "true", "zane-project": project_id, **kwargs}


def get_volume_resource_name(volume_id: str):
    return f"vol-{volume_id}"


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
    ),
    message: str,
):
    current_time = timezone.now()
    print(f"[{current_time.isoformat()}]: {message}")

    match deployment:
        case DockerDeploymentDetails():
            deployment_id = deployment.hash
            service_id = deployment.service.id
        case DeploymentCreateVolumesResult() | DeploymentHealthcheckResult():
            deployment_id = deployment.deployment_hash
            service_id = deployment.service_id
        case _:
            raise TypeError(f"unsupported type {type(deployment)}")

    await SimpleLog.objects.acreate(
        source=SimpleLog.LogSource.SYSTEM,
        level=SimpleLog.LogLevel.INFO,
        content=message,
        time=current_time,
        deployment_id=deployment_id,
        service_id=service_id,
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
    def _get_id_for_deployment(cls, deployment_hash: str):
        return f"{deployment_hash}-url"

    @classmethod
    def get_uri_for_deployment(cls, deployment_hash: str):
        return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{cls._get_id_for_deployment(deployment_hash)}"

    @classmethod
    def _get_request_for_deployment(cls, deployment: DockerDeploymentDetails):
        service = deployment.service
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
            "upstreams": [{"dial": settings.ZANE_API_SERVICE_INTERNAL_DOMAIN}],
        }

        return {
            "@id": cls._get_id_for_deployment(deployment.hash),
            "match": [{"host": [deployment.url]}],
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [
                        {
                            "handle": [
                                protect_deployment_proxy_handler,
                                {
                                    "flush_interval": -1,
                                    "handler": "reverse_proxy",
                                    "upstreams": [
                                        {
                                            "dial": f"{service_name}:{service.http_port.forwarded}"
                                        }
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
    def _get_request_for_service(
        cls,
        url: URLDto,
        current_deployment: DockerDeploymentDetails,
        previous_deployment: DockerDeployment | None,
    ):
        service = current_deployment.service
        http_port = service.http_port
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
                        "server": ["zaneops"],
                        "x-request-id": ["{http.request.uuid}"],
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

        thirty_seconds_in_nano_seconds = 30_000_000_000
        proxy_handlers.append(
            {
                "flush_interval": -1,
                "handler": "reverse_proxy",
                "health_checks": {
                    "passive": {"fail_duration": thirty_seconds_in_nano_seconds}
                },
                "load_balancing": {
                    "retries": 3,
                    "selection_policy": {"policy": "first"},
                },
                "upstreams": [
                    {
                        "dial": f"{service.network_alias}.blue.{settings.ZANE_INTERNAL_DOMAIN}:{http_port.forwarded}"
                    },
                    {
                        "dial": f"{service.network_alias}.green.{settings.ZANE_INTERNAL_DOMAIN}:{http_port.forwarded}"
                    },
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
    def insert_deployment_url(cls, deployment: DockerDeploymentDetails):
        if deployment.url is not None:
            response = requests.get(
                cls.get_uri_for_deployment(deployment.hash),
                timeout=5,
            )

            # if the domain doesn't exist we create the config for the domain
            if response.status_code == status.HTTP_404_NOT_FOUND:
                requests.put(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes/0",
                    headers={"content-type": "application/json"},
                    json=cls._get_request_for_deployment(deployment),
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
            new_url = cls._get_request_for_service(
                url, current_deployment, previous_deployment
            )
            routes.append(new_url)
            routes = cls._sort_routes(routes)

            response = requests.patch(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes",
                headers={"content-type": "application/json", "If-Match": etag},
                json=routes,
                timeout=5,
            )
            if response.status_code == status.HTTP_412_PRECONDITION_FAILED:
                continue
            return

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
        for route in response.json():  # type: dict[str, str]
            if (
                route["@id"].startswith(service.id)
                and route["@id"] not in service_url_ids
            ):
                requests.delete(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{route['@id']}",
                    timeout=5,
                )

    @classmethod
    def remove_deployment_url(cls, deployment_hash: str):
        requests.delete(
            cls.get_uri_for_deployment(deployment_hash),
            timeout=5,
        )


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

        network = self.docker_client.networks.create(
            name=get_network_resource_name(project.id),
            scope="swarm",
            driver="overlay",
            labels=get_resource_labels(project.id),
            attachable=True,
        )
        return network.id

    @activity.defn
    async def attach_network_to_proxy(self, network_id: str):
        proxy_service = ZaneProxyClient.get_service()
        service_spec = proxy_service.attrs["Spec"]
        current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
        network_ids = set(net["Target"] for net in current_networks)
        network_ids.add(network_id)
        await asyncio.to_thread(proxy_service.update, networks=list(network_ids))

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

        archived_docker_services: QuerySet[ArchivedDockerService] = (
            ArchivedDockerService.objects.filter(project=archived_project)
            .select_related("project")
            .prefetch_related("volumes", "urls")
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
                            hash=dpl.get("hash"),
                            url=dpl.get("url"),
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
                print(f"Removed service. YAY !! 🎉")
                try:
                    await delete_schedule(deployment.monitor_schedule_id)
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
        await SimpleLog.objects.filter(service_id=service_details.original_id).adelete()

    @activity.defn
    async def detach_network_from_proxy(
        self, project_details: ArchivedProjectDetails
    ) -> Optional[str]:
        try:
            network_associated_to_project: Network = self.docker_client.networks.get(
                get_network_resource_name(project_id=project_details.original_id)
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                f"Network `{get_network_resource_name(project_id=project_details.original_id)}`"
                f" for project `{project_details.original_id}` does not exist.",
                non_retryable=True,
            )

        proxy_service = ZaneProxyClient.get_service()
        service_spec = proxy_service.attrs["Spec"]
        current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
        network_ids = set(net["Target"] for net in current_networks)

        if network_associated_to_project.id in network_ids:
            network_ids.remove(network_associated_to_project.id)
            proxy_service.update(networks=list(network_ids))

        async def wait_for_service_to_update():
            is_network_found = True
            while is_network_found:
                tasks = proxy_service.tasks(filters={"desired-state": "running"})
                network_names = []
                for task in tasks:
                    network_names += [
                        net["Network"]["Spec"]["Name"]
                        for net in task["NetworksAttachments"]
                    ]

                is_network_found = network_associated_to_project.name in network_names
                if is_network_found:
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    continue

        await wait_for_service_to_update()
        return network_associated_to_project.id

    @activity.defn
    async def remove_project_network(self, project_details: ArchivedProjectDetails):
        try:
            network_associated_to_project: Network = self.docker_client.networks.get(
                get_network_resource_name(project_id=project_details.original_id)
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                f"Network `{get_network_resource_name(project_id=project_details.original_id)}`"
                f" for project `{project_details.original_id}` does not exist.",
                non_retryable=True,
            )

        network_associated_to_project.remove()

    @activity.defn
    async def prepare_deployment(self, deployment: DockerDeploymentDetails):
        try:
            await deployment_log(
                deployment,
                f"Preparing deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}...",
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
            f"Handling cancellation request for deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}...",
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
            f"Deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}"
            f" finished with status {Colors.GREY}{DockerDeployment.DeploymentStatus.CANCELLED}{Colors.ENDC}.",
        )

    @activity.defn
    async def finish_and_save_deployment(
        self, healthcheck_result: DeploymentHealthcheckResult
    ) -> str:
        try:
            deployment: DockerDeployment = (
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
                or await deployment.service.deployments.acount() == 1
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
                await deployment.service.deployments.filter(
                    ~Q(hash=healthcheck_result.deployment_hash)
                ).aupdate(is_current_production=False)
                await deployment.service.deployments.filter(
                    ~Q(hash=healthcheck_result.deployment_hash)
                    & Q(
                        status__in=[
                            DockerDeployment.DeploymentStatus.PREPARING,
                            DockerDeployment.DeploymentStatus.STARTING,
                            DockerDeployment.DeploymentStatus.RESTARTING,
                        ]
                    )
                    & Q(finished_at__isnull=True),
                ).aupdate(
                    finished_at=timezone.now(),
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
                f"Deployment {Colors.YELLOW}{healthcheck_result.deployment_hash}{Colors.ENDC}"
                f" finished with status {status_color}{deployment.status}{Colors.ENDC}.",
            )
            return deployment.status

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

        if latest_production_deployment:
            return SimpleDeploymentDetails(
                hash=latest_production_deployment.hash,
                service_id=latest_production_deployment.service_id,
                project_id=deployment.service.project_id,
                status=latest_production_deployment.status,
                url=latest_production_deployment.url,
            )
        return None

    @activity.defn
    async def get_previous_queued_deployment(self, deployment: DockerDeploymentDetails):
        next_deployment: DockerDeployment = (
            await DockerDeployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(status=DockerDeployment.DeploymentStatus.QUEUED)
            )
            .select_related("service")
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
                deployment=next_deployment,
                auth_token=deployment.auth_token,
            )
        return None

    @activity.defn
    async def cleanup_previous_production_deployment(
        self, deployment: SimpleDeploymentDetails
    ):
        docker_deployment: DockerDeployment | None = (
            await DockerDeployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service_id
            )
            .select_related("service")
            .afirst()
        )

        if docker_deployment is not None:
            docker_deployment.status = DockerDeployment.DeploymentStatus.REMOVED
            await docker_deployment.asave()

            try:
                await delete_schedule(
                    id=docker_deployment.monitor_schedule_id,
                )
            except RPCError:
                # The schedule probably doesn't exist
                pass

    @activity.defn
    async def create_docker_volumes_for_service(
        self, deployment: DockerDeploymentDetails
    ) -> List[VolumeDto]:
        await deployment_log(
            deployment,
            f"Creating volumes for deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}...",
        )
        service = deployment.service
        created_volumes: List[VolumeDto] = []
        for volume in service.docker_volumes:
            try:
                self.docker_client.volumes.get(get_volume_resource_name(volume.id))
            except docker.errors.NotFound:
                created_volumes.append(volume)
                self.docker_client.volumes.create(
                    name=get_volume_resource_name(volume.id),
                    driver="local",
                    labels=get_resource_labels(service.project_id, parent=service.id),
                )

        await deployment_log(
            deployment,
            f"Volumes created succesfully for deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}  ✅",
        )

        return created_volumes

    @activity.defn
    async def delete_created_volumes(self, deployment: DeploymentCreateVolumesResult):
        await deployment_log(
            deployment,
            f"Deleting created volumes for deployment {Colors.YELLOW}{deployment.deployment_hash}{Colors.ENDC}...",
        )
        for volume in deployment.created_volumes:
            try:
                docker_volume = self.docker_client.volumes.get(
                    get_volume_resource_name(volume.id)
                )
            except docker.errors.NotFound:
                pass
            else:
                docker_volume.remove(force=True)

        await deployment_log(
            deployment,
            f"Volumes deleted succesfully for deployment {Colors.YELLOW}{deployment.deployment_hash}{Colors.ENDC}  ✅",
        )

    @activity.defn
    async def close_faulty_db_connections(self):
        """
        This is to fix a bug we encountered when the worker hadn't run any job for a long time,
        after that time, Django lost the DB connections, what is needed is to close the connection
        so that Django can recreate the connection.
        https://stackoverflow.com/questions/31504591/interfaceerror-connection-already-closed-using-django-celery-scrapy
        """
        for conn in db.connections.all():
            conn.close_if_unusable_or_obsolete()

    @activity.defn
    async def scale_down_service_deployment(self, deployment: SimpleDeploymentDetails):
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
            swarm_service.scale(0)

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
            docker_deployment: DockerDeployment | None = (
                await DockerDeployment.objects.filter(
                    hash=deployment.hash, service_id=deployment.service_id
                ).afirst()
            )

            if docker_deployment is not None:
                docker_deployment.status = DockerDeployment.DeploymentStatus.SLEEPING
                await docker_deployment.asave()
                try:
                    await pause_schedule(
                        id=deployment.monitor_schedule_id,
                        note="Paused to prevent zero-downtime deployment",
                    )
                except RPCError:
                    # The schedule probably doesn't exist
                    pass

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
            swarm_service.scale(1)

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
    async def pull_image_for_deployment(self, deployment: DockerDeploymentDetails):
        service = deployment.service
        await deployment_log(
            deployment,
            f"Pulling image {Colors.YELLOW}{service.image}{Colors.ENDC}...",
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
        except docker.errors.ImageNotFound as e:
            raise ApplicationError(non_retryable=True, message=str(e))
        else:
            await deployment_log(
                deployment,
                f"Finished pulling image {Colors.YELLOW}{service.image}{Colors.ENDC} ✅",
            )

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
            # env variables
            envs: list[str] = [
                f"{env.key}={env.value}" for env in service.env_variables
            ]
            # zane-specific-envs
            envs.extend(
                [
                    f"ZANE=1",
                    f"ZANE_DEPLOYMENT_SLOT={deployment.slot}",
                    f"ZANE_DEPLOYMENT_HASH={deployment.unprefixed_hash}",
                    f"ZANE_DEPLOYMENT_TYPE=docker",
                    f"ZANE_PRIVATE_DOMAIN={service.network_alias}",
                    f"ZANE_SERVICE_ID={service.id}",
                    f"ZANE_SERVICE_NAME={service.slug}",
                    f"ZANE_PROJECT_ID={service.project_id}",
                    f"""ZANE_DEPLOYMENT_URL={deployment.url or '""'}""",
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
                # Only include volumes that are not to be deleted
                docker_volume = find_item_in_list(
                    lambda v: v.name == get_volume_resource_name(volume.id),
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

            # ports
            exposed_ports: dict[int, int] = {}
            endpoint_spec: EndpointSpec | None = None

            # We don't expose HTTP ports with docker because they will be handled by caddy directly
            for port in service.non_http_ports:
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
                f"Creating service for the deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}...",
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
                ),
                networks=[
                    NetworkAttachmentConfig(
                        target=get_network_resource_name(service.project_id),
                        aliases=[alias for alias in deployment.network_aliases],
                    ),
                ],
                restart_policy=RestartPolicy(
                    condition="on-failure",
                    max_attempts=3,
                    delay=int(5e9),  # delay is in nanoseconds
                ),
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
            )
            await deployment_log(
                deployment,
                f"Service created succesfully for the deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC} ✅",
            )

    @activity.defn
    async def run_deployment_healthcheck(
        self,
        deployment: DockerDeploymentDetails,
    ) -> tuple[DockerDeployment.DeploymentStatus, str]:
        docker_deployment: DockerDeployment = (
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
            f"Running healthchecks for deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}...",
        )
        while (monotonic() - start_time) < healthcheck_timeout:
            healthcheck_attempts += 1
            healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)

            await deployment_log(
                deployment,
                f"Healtcheck for deployment {Colors.YELLOW}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC}"
                f" | healthcheck_time_left={Colors.YELLOW}{format_seconds(healthcheck_time_left)}{Colors.ENDC} 💓",
            )

            task_list = swarm_service.tasks(
                filters={"label": f"deployment_hash={docker_deployment.hash}"}
            )
            if len(task_list) > 0:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                starting_status = DockerDeployment.DeploymentStatus.STARTING
                # We set the status to restarting, because we get more than one task for this service when we restart it
                if len(task_list) > 1:
                    starting_status = DockerDeployment.DeploymentStatus.RESTARTING

                state_matrix = {
                    DockerSwarmTaskState.NEW: starting_status,
                    DockerSwarmTaskState.PENDING: starting_status,
                    DockerSwarmTaskState.ASSIGNED: starting_status,
                    DockerSwarmTaskState.ACCEPTED: starting_status,
                    DockerSwarmTaskState.READY: starting_status,
                    DockerSwarmTaskState.PREPARING: starting_status,
                    DockerSwarmTaskState.STARTING: starting_status,
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

                if deployment_status == starting_status:
                    docker_deployment.status = starting_status
                    await docker_deployment.asave()

                deployment_status_reason = (
                    most_recent_swarm_task.Status.Err
                    if most_recent_swarm_task.Status.Err is not None
                    else most_recent_swarm_task.Status.Message
                )

                if most_recent_swarm_task.state == DockerSwarmTaskState.SHUTDOWN:
                    status_code = most_recent_swarm_task.Status.ContainerStatus.ExitCode
                    if (
                        status_code is not None and status_code != exited_without_error
                    ) or most_recent_swarm_task.Status.Err is not None:
                        deployment_status = DockerDeployment.DeploymentStatus.UNHEALTHY

                if most_recent_swarm_task.state == DockerSwarmTaskState.RUNNING:
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
                                )  # type: int, bytes

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
                                scheme = (
                                    "https"
                                    if settings.ENVIRONMENT == settings.PRODUCTION_ENV
                                    else "http"
                                )
                                full_url = f"{scheme}://{docker_deployment.url + healthcheck.value}"
                                response = requests.get(
                                    full_url,
                                    headers={
                                        "Authorization": f"Token {deployment.auth_token}"
                                    },
                                    timeout=min(healthcheck_time_left, 5),
                                )
                                if response.status_code == status.HTTP_200_OK:
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
                            break

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
                        f"Healtcheck for deployment {Colors.YELLOW}{docker_deployment.hash}{Colors.ENDC}"
                        f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                        f"| finished with status {status_color}{deployment_status}{Colors.ENDC} ✅",
                    )
                    return deployment_status, deployment_status_reason

            await deployment_log(
                deployment,
                f"Healtcheck for deployment deployment {Colors.YELLOW}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                f"| FAILED, Retrying in {Colors.YELLOW}{format_seconds(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)}{Colors.ENDC} 🔄",
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)

        status_color = (
            Colors.GREEN
            if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY
            else Colors.RED
        )
        await deployment_log(
            deployment,
            f"Healtcheck for deployment {Colors.YELLOW}{docker_deployment.hash}{Colors.ENDC}"
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
        if service.http_port is not None:
            ZaneProxyClient.insert_deployment_url(deployment)

    @activity.defn
    async def expose_docker_service_to_http(
        self,
        deployment: DockerDeploymentDetails,
    ):
        service = deployment.service
        if service.http_port is not None:
            await deployment_log(
                deployment,
                f"Configuring service URLs for deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC}...",
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
                f"Service URLs for deployment {Colors.YELLOW}{deployment.hash}{Colors.ENDC} configured successfully ✅",
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
            get_volume_resource_name(volume.id) for volume in service.docker_volumes
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
    async def remove_old_urls(self, deployment: DockerDeploymentDetails):
        ZaneProxyClient.cleanup_old_service_urls(deployment)

    @activity.defn
    async def unexpose_docker_service_from_http(
        self, service_details: ArchivedServiceDetails
    ):
        for url in service_details.urls:
            ZaneProxyClient.remove_service_url(service_details.original_id, url)

        for deployment in service_details.deployments:
            if deployment.url is not None:
                ZaneProxyClient.remove_deployment_url(deployment.hash)

    @activity.defn
    async def unexpose_docker_deployment_from_http(
        self, deployment: DockerDeploymentDetails
    ):
        if deployment.url is not None:
            ZaneProxyClient.remove_deployment_url(deployment.hash)

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
    async def create_deployment_healthcheck_schedule(
        self, deployment: DockerDeploymentDetails
    ):
        try:
            docker_deployment: DockerDeployment = (
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
                "Cannot save a non existent deployment.",
                non_retryable=True,
            )
        else:
            healthcheck: Optional[HealthCheck] = docker_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=deployment.hash,
                    service_id=deployment.service.id,
                    project_id=deployment.service.project_id,
                    url=deployment.url,
                ),
                auth_token=deployment.auth_token,
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
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
            )
