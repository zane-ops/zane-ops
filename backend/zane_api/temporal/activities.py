import asyncio
import json
from typing import List, Optional

from rest_framework import status
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
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
    )
    from docker.models.networks import Network
    import requests
    from docker.types import EndpointSpec, NetworkAttachmentConfig, RestartPolicy
    from django.conf import settings
    from django.utils import timezone
    from time import monotonic
    from django.db.models import Q
    from ..utils import (
        strip_slash_if_exists,
        find_item_in_list,
        format_seconds,
        DockerSwarmTask,
        DockerSwarmTaskState,
    )

from ..dtos import (
    URLDto,
    PortConfigurationDto,
    DockerServiceSnapshot,
    DeploymentChangeDto,
)
from .shared import (
    ProjectDetails,
    ArchivedProjectDetails,
    ArchivedServiceDetails,
    SimpleDeploymentDetails,
    DeploymentDetails,
    DeploymentHealthcheckResult,
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


def get_volume_resource_name(volume_id: str):
    return f"vol-{volume_id}"


def get_swarm_service_name_for_deployment(
    deployment_hash: str,
    project_id: str,
    service_id: str,
):
    return f"srv-{project_id}-{service_id}-{deployment_hash}"


def get_proxy_service():
    client = get_docker_client()
    services_list = client.services.list(filters={"label": ["zane.role=proxy"]})

    if len(services_list) == 0:
        raise docker.errors.NotFound("Proxy Service is not up")
    proxy_service = services_list[0]
    return proxy_service


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


def get_caddy_uri_for_url(url: URLDto | URL):
    return f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{get_caddy_id_for_url(url)}"


def get_caddy_id_for_url(url: URLDto | URL):
    normalized_path = strip_slash_if_exists(
        url.base_path, strip_end=True, strip_start=True
    ).replace("/", "-")

    if len(normalized_path) == 0:
        normalized_path = "*"

    return f"{url.domain}-{normalized_path}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}"


def get_caddy_request_for_domain(domain: str):
    return {
        "@id": f"{domain}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}",
        "match": [{"host": [domain]}],
        "handle": [
            {
                "handler": "subroute",
                "routes": [],
            }
        ],
    }


def get_caddy_request_for_deployment_url(
    url: str, service_name: str, forwarded_http_port: int
):
    return {
        "@id": f"{url}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}",
        "match": [{"host": [url]}],
        "handle": [
            {
                "handler": "subroute",
                "routes": [
                    {
                        "handle": [
                            {
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
                                            "X-Forwarded-Method": [
                                                "{http.request.method}"
                                            ],
                                            "X-Forwarded-Uri": ["{http.request.uri}"],
                                        }
                                    }
                                },
                                "rewrite": {
                                    "method": "GET",
                                    "uri": "/api/auth/me/with-token",
                                },
                                "upstreams": [
                                    {"dial": settings.ZANE_API_SERVICE_INTERNAL_DOMAIN}
                                ],
                            },
                            {
                                "flush_interval": -1,
                                "handler": "reverse_proxy",
                                "upstreams": [
                                    {"dial": f"{service_name}:{forwarded_http_port}"}
                                ],
                            },
                        ]
                    }
                ],
            }
        ],
    }


def get_caddy_request_for_url(
    url: URLDto,
    service: DockerServiceSnapshot,
    http_port: PortConfigurationDto,
    current_deployment_hash: str = None,
    current_deployment_slot: str = None,
    service_id: str = None,
    previous_deployment_hash: str = None,
    previous_deployment_slot: str = None,
):
    blue_hash = None
    green_hash = None

    if current_deployment_slot == "BLUE":
        blue_hash = current_deployment_hash
    elif current_deployment_slot == "GREEN":
        green_hash = current_deployment_hash

    if previous_deployment_slot == "BLUE":
        blue_hash = previous_deployment_hash
    elif previous_deployment_slot == "GREEN":
        green_hash = previous_deployment_hash

    proxy_handlers = [
        {
            "handler": "log_append",
            "key": "zane_service_id",
            "value": service_id,
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
                    (
                        "/*"
                        if url.base_path == "/"
                        else f"{strip_slash_if_exists(url.base_path, strip_end=True, strip_start=False)}*"
                    )
                ],
            }
        ],
    }


class DockerSwarmActivities:
    DEFAULT_TIMEOUT_FOR_DOCKER_EVENTS = 30  # seconds

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
        proxy_service = get_proxy_service()
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
                        SimpleDeploymentDetails(
                            hash=deployment_hash,
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for deployment_hash in service.deployment_hashes
                    ],
                )
            )
        return archived_services

    @activity.defn
    async def cleanup_docker_service_resources(
        self, service_details: ArchivedServiceDetails
    ):
        for deployment in service_details.deployments:
            try:
                swarm_service = self.docker_client.services.get(
                    get_swarm_service_name_for_deployment(
                        deployment_hash=deployment.id,
                        service_id=deployment.service_id,
                        project_id=deployment.project_id,
                    )
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
            network_associated_to_project: Network = self.docker_client.networks.get(
                get_network_resource_name(project_id=project_details.original_id)
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                f"Network `{get_network_resource_name(project_id=project_details.original_id)}`"
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

        async def wait_for_service_to_update():
            proxy = get_proxy_service()
            is_network_found = True
            while is_network_found:
                tasks = proxy.tasks(filters={"desired-state": "running"})
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
    async def prepare_deployment(self, deployment: DeploymentDetails):
        try:
            docker_deployment: DockerDeployment = await DockerDeployment.objects.aget(
                hash=deployment.hash
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
    async def finish_and_save_deployment(
        self, healthcheck_result: DeploymentHealthcheckResult
    ) -> Optional[SimpleDeploymentDetails]:
        try:
            docker_deployment: DockerDeployment = (
                await DockerDeployment.objects.filter(
                    hash=healthcheck_result.deployment_hash
                )
                .select_related("service")
                .afirst()
            )

            if docker_deployment is None:
                raise DockerDeployment.DoesNotExist(
                    f"Docker deployment with hash='{healthcheck_result.deployment_hash}' does not exist."
                )

            docker_deployment.status_reason = healthcheck_result.reason
            if (
                healthcheck_result.status == DockerDeployment.DeploymentStatus.HEALTHY
                or await docker_deployment.service.deployments.acount() == 1
            ):
                docker_deployment.is_current_production = True

            docker_deployment.status = (
                DockerDeployment.DeploymentStatus.HEALTHY
                if healthcheck_result.status
                == DockerDeployment.DeploymentStatus.HEALTHY
                else DockerDeployment.DeploymentStatus.FAILED
            )

            docker_deployment.finished_at = timezone.now()
            await docker_deployment.asave()

            if docker_deployment.is_current_production:
                await docker_deployment.service.deployments.filter(
                    ~Q(hash=healthcheck_result.deployment_hash)
                ).aupdate(is_current_production=False)

            previous_deployment: DockerDeployment | None = await (
                DockerDeployment.objects.filter(
                    Q(service_id=docker_deployment.service.id)
                    & Q(queued_at__lt=docker_deployment.queued_at)
                    & ~Q(hash=docker_deployment.hash)
                )
                .order_by("-queued_at")
                .afirst()
            )

            if previous_deployment is not None:
                return SimpleDeploymentDetails(
                    hash=previous_deployment.hash,
                    service_id=previous_deployment.service_id,
                    project_id=docker_deployment.service.project_id,
                )
        except DockerDeployment.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent deployment.",
                non_retryable=True,
            )

    @activity.defn
    async def cleanup_previous_deployment(self, deployment: SimpleDeploymentDetails):
        await DockerDeployment.objects.filter(hash=deployment.hash).aupdate(
            status=DockerDeployment.DeploymentStatus.REMOVED
        )

    @activity.defn
    async def create_docker_volumes_for_service(self, deployment: DeploymentDetails):
        service = deployment.service
        for volume in service.docker_volumes:
            try:
                self.docker_client.volumes.get(get_volume_resource_name(volume.id))
            except docker.errors.NotFound:
                self.docker_client.volumes.create(
                    name=get_volume_resource_name(volume.id),
                    driver="local",
                    labels=get_resource_labels(service.project_id, parent=service.id),
                )

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
            raise ApplicationError(
                "Cannot scale down an nonexistent deployment.",
                non_retryable=True,
            )
        else:
            swarm_service.scale(0)

            async def wait_for_service_to_be_down():
                print(f"waiting for service `{swarm_service.name=}` to be down...")
                task_list = swarm_service.tasks()
                while len(task_list) > 0:
                    print(
                        f"service `{swarm_service.name=}` is not down yet, "
                        + f"retrying in `{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}` seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = swarm_service.tasks()
                print(f"service `{swarm_service.name=}` is down, YAY !! 🎉")

            await wait_for_service_to_be_down()

    @activity.defn
    async def create_swarm_service_for_docker_deployment(
        self, deployment: DeploymentDetails
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
            self.docker_client.images.pull(
                repository=service.image,
                auth_config=service.credentials,
            )

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
                    delay=5,
                ),
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
            )

    @activity.defn
    async def run_deployment_healthcheck(
        self,
        deployment: DeploymentDetails,
    ) -> tuple[DockerDeployment.DeploymentStatus, str]:
        docker_deployment: DockerDeployment = (
            await DockerDeployment.objects.filter(hash=deployment.hash)
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
        while (monotonic() - start_time) < healthcheck_timeout:
            healthcheck_attempts += 1
            healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)

            # TODO (#67) : send system logs when the state changes
            print(
                f"Healtcheck for {docker_deployment.hash=} | ATTEMPT #{healthcheck_attempts} "
                f"| healthcheck_time_left={format_seconds(healthcheck_time_left)} 💓"
            )

            task_list = swarm_service.tasks(
                filters={"label": f"deployment_hash={docker_deployment.hash}"}
            )
            if len(task_list) == 0:
                if docker_deployment.status in [
                    DockerDeployment.DeploymentStatus.HEALTHY,
                    DockerDeployment.DeploymentStatus.STARTING,
                    DockerDeployment.DeploymentStatus.RESTARTING,
                ]:
                    return (
                        DockerDeployment.DeploymentStatus.UNHEALTHY,
                        "An Unknown error occurred, did you manually scale down the service ?",
                    )
            else:
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

                        except TimeoutError as e:
                            deployment_status = (
                                DockerDeployment.DeploymentStatus.UNHEALTHY
                            )
                            deployment_status_reason = str(e)
                            break

                healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)
                if (
                    deployment_status != DockerDeployment.DeploymentStatus.HEALTHY
                    and healthcheck_time_left
                    > settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL
                ):
                    print(
                        f"Healtcheck for deployment {docker_deployment.hash} | ATTEMPT #{healthcheck_attempts} | FAILED,"
                        + f" Retrying in {format_seconds(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)} 🔄"
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    continue

                print(
                    f"Healtcheck for {docker_deployment.hash=} | ATTEMPT #{healthcheck_attempts} "
                    f"| finished with {deployment_status=} ✅"
                )
                return deployment_status, deployment_status_reason
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
        return deployment_status, deployment_status_reason

    @activity.defn
    async def expose_docker_service_deployment_to_http(
        self,
        deployment: DeploymentDetails,
    ):
        # add URL conf for deployment
        service = deployment.service
        if service.http_port is not None:
            if deployment.url is not None:
                response = requests.get(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{deployment.url}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}",
                    timeout=5,
                )

                # if the domain doesn't exist we create the config for the domain
                if response.status_code == status.HTTP_404_NOT_FOUND:
                    requests.put(
                        f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes/0",
                        headers={"content-type": "application/json"},
                        json=get_caddy_request_for_deployment_url(
                            url=deployment.url,
                            service_name=get_swarm_service_name_for_deployment(
                                deployment_hash=deployment.hash,
                                project_id=deployment.service.project_id,
                                service_id=deployment.service.id,
                            ),
                            forwarded_http_port=service.http_port.forwarded,
                        ),
                        timeout=5,
                    )

    @activity.defn
    async def expose_docker_service_to_http(
        self,
        deployment: DeploymentDetails,
    ):
        service = deployment.service
        if service.http_port is not None:
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
                response = requests.get(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}",
                    timeout=5,
                )

                # if the domain doesn't exist we create the config for the domain
                if response.status_code == status.HTTP_404_NOT_FOUND:
                    requests.put(
                        f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-url-root/routes/0",
                        headers={"content-type": "application/json"},
                        json=get_caddy_request_for_domain(url.domain),
                        timeout=5,
                    )

                # now we create or modify the config for the URL
                response = requests.get(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}/handle/0/routes"
                )
                routes = list(
                    filter(
                        lambda route: route["@id"] != get_caddy_id_for_url(url),
                        response.json(),
                    )
                )
                routes.append(
                    get_caddy_request_for_url(
                        url,
                        service,
                        service.http_port,
                        current_deployment_hash=deployment.hash,
                        current_deployment_slot=deployment.slot,
                        service_id=deployment.service.id,
                        previous_deployment_hash=(
                            previous_deployment.hash
                            if previous_deployment is not None
                            else None
                        ),
                        previous_deployment_slot=(
                            previous_deployment.slot
                            if previous_deployment is not None
                            else None
                        ),
                    )
                )
                routes = sort_proxy_routes(routes)

                requests.patch(
                    f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}{settings.CADDY_PROXY_CONFIG_ID_SUFFIX}/handle/0/routes",
                    headers={"content-type": "application/json"},
                    json=routes,
                    timeout=5,
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
            raise ApplicationError(
                "Cannot scale down a nonexistent deployment", non_retryable=True
            )
        else:
            swarm_service.scale(0)

            async def wait_for_service_to_be_down():
                print(f"waiting for service {swarm_service.name=} to be down...")
                task_list = swarm_service.tasks()
                while len(task_list) > 0:
                    print(
                        f"service {swarm_service.name=} is not down yet, "
                        + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = swarm_service.tasks()
                print(f"service {swarm_service.name=} is down, YAY !! 🎉")

            await wait_for_service_to_be_down()
            swarm_service.remove()

    @activity.defn
    async def remove_old_docker_volumes(self, deployment: DeploymentDetails):
        for volume_change in filter(
            lambda change: change.field == DockerDeploymentChange.ChangeField.VOLUMES
            and change.type == DockerDeploymentChange.ChangeType.DELETE,
            deployment.changes,
        ):  # type: DeploymentChangeDto
            try:
                volume = self.docker_client.volumes.get(
                    get_volume_resource_name(volume_change.item_id)
                )
            except docker.errors.NotFound:
                # the volume has already been deleted, do nothing
                pass
            else:
                volume.remove(force=True)

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
                        get_caddy_uri_for_url(url),
                        timeout=5,
                    )

        for url in service_details.deployment_urls:
            requests.delete(
                f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url}",
                timeout=5,
            )
