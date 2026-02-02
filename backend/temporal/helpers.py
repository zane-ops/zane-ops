import asyncio
import os
import shutil

from typing import Any, Dict, List, Literal, TypedDict, cast
from docker.models.services import Service as DockerService


from .shared import DeploymentDetails, ContainerMetrics

from zane_api.utils import (
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
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
)
from zane_api.utils import replace_placeholders, DockerSwarmTask, DockerSwarmTaskState
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
    ComposeStackServiceStatus,
    ComposeStackSnapshot,
)
from temporalio import activity

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
                        "commit_sha": deployment.commit_sha,
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
    "GIT_COMMIT_SHA",
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

    # Determine status based on mode
    is_job = mode_type in ["replicated-job", "global-job"]

    # Get counts from ServiceStatus
    running_replicas = service_status["RunningTasks"]
    desired_replicas = service_status["DesiredTasks"]
    completed_replicas = service_status.get("CompletedTasks", 0)

    # Get all tasks for the tasks list
    tasks = [DockerSwarmTask.from_dict(task) for task in service.tasks()]

    if is_job:
        # For jobs, healthy means completed >= desired
        status = (
            ComposeStackServiceStatus.COMPLETE
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
                "id": task.ID,
                "status": task.state.value,
                "image": task.image,
                "message": task.message,
                "exit_code": task.exit_code,
            }
            for task in tasks
        ],
    }


async def collect_swarm_service_metrics(
    service: DockerService,
    docker_client: docker.DockerClient,
    single_replica: bool = False,
):
    service_mode = service.attrs["Spec"]["Mode"]

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

    # ignore collecting metrics from jobs as they are not long running
    if mode_type.endswith("job"):
        return None

    task_list = [
        DockerSwarmTask.from_dict(task)
        for task in service.tasks(filters={"desired-state": "running"})
    ]
    if len(task_list) == 0:
        return None
    else:
        if single_replica:
            most_recent_swarm_task = max(
                task_list,
                key=lambda task: task.Version.Index,
            )

            if most_recent_swarm_task.container_id is not None:
                return await collect_container_metrics(
                    most_recent_swarm_task.container_id, docker_client
                )
        else:
            metrics = await asyncio.gather(
                *[
                    collect_container_metrics(task.container_id, docker_client)
                    for task in task_list
                    if task.container_id is not None
                ]
            )
            filtered_metrics = [metric for metric in metrics if metric is not None]

            if len(filtered_metrics) == 0:
                return None

            total_metrics = ContainerMetrics(
                cpu_percent=0,
                memory_bytes=0,
                net_tx_bytes=0,
                net_rx_bytes=0,
                disk_read_bytes=0,
                disk_writes_bytes=0,
            )

            for metric in filtered_metrics:
                total_metrics.cpu_percent += metric.cpu_percent
                total_metrics.memory_bytes += metric.memory_bytes
                total_metrics.net_tx_bytes += metric.net_tx_bytes
                total_metrics.net_rx_bytes += metric.net_rx_bytes
                total_metrics.disk_read_bytes += metric.disk_read_bytes
                total_metrics.disk_writes_bytes += metric.disk_writes_bytes

            return total_metrics


async def collect_container_metrics(
    container_id: str, docker_client: docker.DockerClient
):
    try:
        container = docker_client.containers.get(container_id)
    except docker.errors.NotFound:
        return None  # this container may have been deleted already
    else:
        if container.status != "running":
            return  # we cannot get the stats of a dead container

        stats = container.stats(stream=False)

        # Calculate CPU usage percentage
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        cpu_percent: float = (
            (cpu_delta / system_delta) * stats["cpu_stats"]["online_cpus"] * 100
        )

        # Memory usage
        memory_usage: int = stats["memory_stats"]["usage"]

        # Network usage
        rx_bytes: int = sum(
            network["rx_bytes"] for network in stats["networks"].values()
        )
        tx_bytes: int = sum(
            network["tx_bytes"] for network in stats["networks"].values()
        )

        # Disk I/O usage
        read_bytes: int = sum(
            io.get("value", 0)
            for io in (
                stats.get("blkio_stats", {}).get("io_service_bytes_recursive", []) or []
            )
            if io.get("op") == "read"
        )

        write_bytes: int = sum(
            io["value"]
            for io in (
                stats.get("blkio_stats", {}).get("io_service_bytes_recursive", []) or []
            )
            if io["op"] == "write"
        )

        return ContainerMetrics(
            cpu_percent=cpu_percent,
            memory_bytes=memory_usage,
            disk_read_bytes=read_bytes,
            disk_writes_bytes=write_bytes,
            net_rx_bytes=rx_bytes,
            net_tx_bytes=tx_bytes,
        )


async def send_regular_heartbeat(name: str):
    """
    We want this activity to be cancellable,
    for activities to be cancellable, they need to send regular heartbeats:
    https://docs.temporal.io/develop/python/cancellation#cancel-activity
    """
    while True:
        activity.heartbeat(f"Heartbeat from `{name}()`...")
        await asyncio.sleep(0.1)
