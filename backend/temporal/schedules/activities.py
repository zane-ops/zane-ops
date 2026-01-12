import asyncio
from datetime import timedelta
from typing import Any, Dict, List, cast
from rest_framework import status
from temporalio import workflow, activity
from temporalio.exceptions import ApplicationError


from ..shared import (
    CleanupResult,
    HealthcheckDeploymentDetails,
    DeploymentResult,
    ServiceMetricsResult,
    SimpleDeploymentDetails,
    RegistrySnaphot,
    ComposeStackSnapshot,
    RegistryHealthCheckResult,
    ComposeStackHealthcheckResult,
)

with workflow.unsafe.imports_passed_through():
    import requests
    from django.conf import settings
    from django.utils import timezone
    import docker
    import docker.errors
    from django import db
    from django.db.models import Q
    from zane_api.models import Deployment, HealthCheck, ServiceMetrics
    from zane_api.utils import (
        DockerSwarmTaskState,
        DockerSwarmTask,
        Colors,
        escape_ansi,
        excerpt,
    )
    from search.loki_client import LokiSearchClient
    from search.dtos import RuntimeLogDto, RuntimeLogLevel, RuntimeLogSource
    from container_registry.models import BuildRegistry
    from compose.models import ComposeStack
    from compose.dtos import ComposeStackServiceStatus, ComposeStackServiceStatusDto
    from docker.models.services import Service as DockerService

docker_client: docker.DockerClient | None = None


def get_docker_client():
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


def get_swarm_service_name_for_deployment(
    deployment_hash: str,
    project_id: str,
    service_id: str,
):
    return f"srv-{project_id}-{service_id}-{deployment_hash}"


async def deployment_log(deployment: SimpleDeploymentDetails, message: str, error=True):
    current_time = timezone.now()
    print(f"[{current_time.isoformat()}]: {message}")

    search_client = LokiSearchClient(host=settings.LOKI_HOST)
    # This is the max number of characters that we show in color on the frontend
    MAX_COLORED_CHARS = 1000
    search_client.insert(
        document=RuntimeLogDto(
            source=RuntimeLogSource.SYSTEM,
            level=RuntimeLogLevel.ERROR if error else RuntimeLogLevel.INFO,
            content=excerpt(message, MAX_COLORED_CHARS),
            content_text=excerpt(escape_ansi(message), MAX_COLORED_CHARS),
            time=current_time,
            created_at=current_time,
            deployment_id=deployment.hash,
            service_id=deployment.service_id,
        ),
    )


@activity.defn
async def close_faulty_db_connections():
    """
    This is to fix a bug we encountered when the worker hadn't run any job for a long time,
    after that time, Django lost the DB connections, what is needed is to close the connection
    so that Django can recreate the connection.
    https://stackoverflow.com/questions/31504591/interfaceerror-connection-already-closed-using-django-celery-scrapy
    """
    for conn in db.connections.all():
        conn.close_if_unusable_or_obsolete()


class MonitorDockerDeploymentActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def run_deployment_monitor_healthcheck(
        self,
        details: HealthcheckDeploymentDetails,
    ) -> tuple[Deployment.DeploymentStatus, str]:
        try:
            deployment = (
                await Deployment.objects.filter(
                    hash=details.deployment.hash,
                )
                .select_related("service")
                .aget()
            )

            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=details.deployment.hash,
                    project_id=details.deployment.project_id,
                    service_id=details.deployment.service_id,
                )
            )
        except (docker.errors.NotFound, Deployment.DoesNotExist):
            raise ApplicationError(
                "Cannot run a healthcheck on an nonexistent deployment.",
                non_retryable=True,
            )
        else:
            if deployment.status == Deployment.DeploymentStatus.SLEEPING:
                return (
                    Deployment.DeploymentStatus.SLEEPING,
                    "Deployment is sleeping, skipping monitoring health check ",
                )

            healthcheck = details.healthcheck

            healthcheck_timeout = (
                healthcheck.timeout_seconds
                if healthcheck is not None
                else settings.DEFAULT_HEALTHCHECK_TIMEOUT
            )

            task_list = swarm_service.tasks(
                filters={
                    "label": f"deployment_hash={details.deployment.hash}",
                    "desired-state": "running",
                }
            )
            if len(task_list) == 0:
                deployment_status = Deployment.DeploymentStatus.UNHEALTHY
                deployment_status_reason = "Error: The service is down, did you manually scale down the service ?"
            else:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                state_matrix = {
                    DockerSwarmTaskState.NEW: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PENDING: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ASSIGNED: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ACCEPTED: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.READY: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PREPARING: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.STARTING: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.RUNNING: Deployment.DeploymentStatus.HEALTHY,
                    DockerSwarmTaskState.COMPLETE: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.FAILED: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.SHUTDOWN: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.REJECTED: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.ORPHANED: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.REMOVE: Deployment.DeploymentStatus.UNHEALTHY,
                }

                exited_without_error = 0
                deployment_status = state_matrix[most_recent_swarm_task.state]

                all_tasks = swarm_service.tasks(
                    filters={
                        "label": f"deployment_hash={details.deployment.hash}",
                    }
                )
                # We set the status to restarting, because we get more than one task for this service when we restart it
                if (
                    deployment_status == Deployment.DeploymentStatus.STARTING
                    and len(all_tasks) > 1
                ):
                    deployment_status = Deployment.DeploymentStatus.RESTARTING
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
                        deployment_status = Deployment.DeploymentStatus.UNHEALTHY

                if (
                    most_recent_swarm_task.state == DockerSwarmTaskState.RUNNING
                    and most_recent_swarm_task.container_id is not None
                ):
                    if healthcheck is not None:
                        try:
                            print(
                                f"Running custom healthcheck {healthcheck.type=} - {healthcheck.value=}"
                            )
                            container = self.docker_client.containers.get(
                                most_recent_swarm_task.container_id
                            )
                            if healthcheck.type == HealthCheck.HealthCheckType.COMMAND:
                                exit_code, output = container.exec_run(
                                    cmd=healthcheck.value,
                                    stdout=True,
                                    stderr=True,
                                    stdin=False,
                                )

                                if exit_code == 0:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.HEALTHY
                                    )
                                else:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.UNHEALTHY
                                    )
                                deployment_status_reason = output.decode("utf-8")
                            else:
                                container_networks = container.attrs["NetworkSettings"][
                                    "Networks"
                                ]
                                dns_names = container_networks["zane"]["DNSNames"]
                                container_hostname_in_network: str = next(
                                    host
                                    for host in dns_names
                                    if container.id.startswith(host)  # type: ignore
                                )
                                full_url = f"http://{container_hostname_in_network}:{healthcheck.associated_port}{healthcheck.value}"
                                response = requests.get(
                                    full_url,
                                    timeout=healthcheck_timeout,
                                )
                                if response.status_code == status.HTTP_200_OK:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.HEALTHY
                                    )
                                else:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.UNHEALTHY
                                    )
                                deployment_status_reason = response.content.decode(
                                    "utf-8"
                                )

                        except TimeoutError as e:
                            deployment_status = Deployment.DeploymentStatus.UNHEALTHY
                            deployment_status_reason = str(e)

            status_color = (
                Colors.GREEN
                if deployment_status == Deployment.DeploymentStatus.HEALTHY
                else Colors.RED
            )

            print(
                f"Healthcheck for {details.deployment.hash=} | finished with {deployment_status=} 🏁"
            )

            unhealthy = deployment_status != Deployment.DeploymentStatus.HEALTHY

            if unhealthy:
                if deployment_status == Deployment.DeploymentStatus.UNHEALTHY:
                    status_flag = "❌"
                else:
                    status_flag = "🏁"

                await deployment_log(
                    deployment=details.deployment,
                    message=f"Monitoring Healthcheck for deployment {Colors.ORANGE}{details.deployment.hash}{Colors.ENDC} "
                    f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC}",
                )
                await deployment_log(
                    deployment=details.deployment,
                    message=f"Monitoring Healthcheck for deployment {Colors.ORANGE}{details.deployment.hash}{Colors.ENDC} "
                    f"| finished with status {status_color}{deployment_status}{Colors.ENDC} {status_flag}",
                )

            return deployment_status, deployment_status_reason

    @activity.defn
    async def save_deployment_status(self, healthcheck_result: DeploymentResult):
        await Deployment.objects.filter(
            Q(hash=healthcheck_result.deployment_hash, is_current_production=True)
            & ~Q(
                status__in=[
                    Deployment.DeploymentStatus.SLEEPING,
                    Deployment.DeploymentStatus.REMOVED,
                ]
            )
        ).aupdate(
            status_reason=healthcheck_result.reason,
            status=healthcheck_result.status,
            updated_at=timezone.now(),
        )


class DockerDeploymentStatsActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def get_deployment_stats(
        self, details: SimpleDeploymentDetails
    ) -> ServiceMetricsResult | None:
        try:
            docker_deployment = await Deployment.objects.aget(
                hash=details.hash,
            )
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=details.hash,
                    project_id=details.project_id,
                    service_id=details.service_id,
                )
            )
        except (docker.errors.NotFound, Deployment.DoesNotExist):
            raise ApplicationError(
                "Cannot run a healthcheck on an nonexistent deployment.",
                non_retryable=True,
            )
        else:
            if docker_deployment.status == Deployment.DeploymentStatus.SLEEPING:
                return None

            task_list = swarm_service.tasks(
                filters={
                    "label": f"deployment_hash={details.hash}",
                    "desired-state": "running",
                }
            )
            if len(task_list) == 0:
                return None
            else:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                if most_recent_swarm_task.container_id is not None:
                    try:
                        container = self.docker_client.containers.get(
                            most_recent_swarm_task.container_id
                        )
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
                            (cpu_delta / system_delta)
                            * stats["cpu_stats"]["online_cpus"]
                            * 100
                        )

                        # Memory usage
                        memory_usage: int = stats["memory_stats"]["usage"]

                        # Network usage
                        rx_bytes: int = sum(
                            network["rx_bytes"]
                            for network in stats["networks"].values()
                        )
                        tx_bytes: int = sum(
                            network["tx_bytes"]
                            for network in stats["networks"].values()
                        )

                        # Disk I/O usage
                        read_bytes: int = sum(
                            io.get("value", 0)
                            for io in (
                                stats.get("blkio_stats", {}).get(
                                    "io_service_bytes_recursive", []
                                )
                                or []
                            )
                            if io.get("op") == "read"
                        )

                        write_bytes: int = sum(
                            io["value"]
                            for io in (
                                stats.get("blkio_stats", {}).get(
                                    "io_service_bytes_recursive", []
                                )
                                or []
                            )
                            if io["op"] == "write"
                        )

                        return ServiceMetricsResult(
                            cpu_percent=cpu_percent,
                            memory_bytes=memory_usage,
                            disk_read_bytes=read_bytes,
                            disk_writes_bytes=write_bytes,
                            net_rx_bytes=rx_bytes,
                            net_tx_bytes=tx_bytes,
                            deployment=details,
                        )

    @activity.defn
    async def save_deployment_stats(self, metrics: ServiceMetricsResult):
        deployment = (
            await Deployment.objects.filter(
                hash=metrics.deployment.hash,
            )
            .select_related("service")
            .afirst()
        )
        if deployment is None:
            raise ApplicationError(
                "Cannot save metrics for a non existent deployment.",
                non_retryable=True,
            )

        await ServiceMetrics.objects.acreate(
            cpu_percent=metrics.cpu_percent,
            memory_bytes=metrics.memory_bytes,
            disk_read_bytes=metrics.disk_read_bytes,
            disk_writes_bytes=metrics.disk_writes_bytes,
            net_rx_bytes=metrics.net_rx_bytes,
            net_tx_bytes=metrics.net_tx_bytes,
            deployment=deployment,
            service=deployment.service,
        )


class CleanupActivities:
    @activity.defn
    async def cleanup_service_metrics(self) -> CleanupResult:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deleted = await ServiceMetrics.objects.filter(
            created_at__lt=today - timedelta(days=30)
        ).adelete()
        return CleanupResult(deleted_count=deleted[0])


class MonitorRegistryDeploymentActivites:
    def __init__(self):
        self.docker = get_docker_client()

    @activity.defn
    async def run_registry_swarm_healthcheck(self, registry: RegistrySnaphot):
        try:
            swarm_service = self.docker.services.get(registry.swarm_service_name)
        except docker.errors.NotFound:
            raise ApplicationError("This registry has not been deployed yet")
        else:
            task_list = swarm_service.tasks(
                filters={
                    "desired-state": "running",
                }
            )
            if len(task_list) == 0:
                deployment_status = BuildRegistry.RegistryHealthStatus.UNHEALTHY
                deployment_status_reason = "Error: The service is down, did you manually scale down the service ?"
            else:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                state_matrix = {
                    DockerSwarmTaskState.NEW: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.PENDING: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.ASSIGNED: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.ACCEPTED: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.READY: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.PREPARING: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.STARTING: BuildRegistry.RegistryHealthStatus.STARTING,
                    DockerSwarmTaskState.RUNNING: BuildRegistry.RegistryHealthStatus.HEALTHY,
                    DockerSwarmTaskState.COMPLETE: BuildRegistry.RegistryHealthStatus.UNHEALTHY,
                    DockerSwarmTaskState.FAILED: BuildRegistry.RegistryHealthStatus.UNHEALTHY,
                    DockerSwarmTaskState.SHUTDOWN: BuildRegistry.RegistryHealthStatus.UNHEALTHY,
                    DockerSwarmTaskState.REJECTED: BuildRegistry.RegistryHealthStatus.UNHEALTHY,
                    DockerSwarmTaskState.ORPHANED: BuildRegistry.RegistryHealthStatus.UNHEALTHY,
                    DockerSwarmTaskState.REMOVE: BuildRegistry.RegistryHealthStatus.UNHEALTHY,
                }
                deployment_status = state_matrix[most_recent_swarm_task.state]

                all_tasks = [
                    task
                    for task in swarm_service.tasks()
                    if DockerSwarmTask.from_dict(task).state
                    == DockerSwarmTaskState.RUNNING
                ]
                # We set the status to restarting, because we get more than one task for this service when we restart it
                if (
                    deployment_status == Deployment.DeploymentStatus.STARTING
                    and len(all_tasks) > 1
                ):
                    deployment_status = Deployment.DeploymentStatus.RESTARTING

                deployment_status_reason = (
                    most_recent_swarm_task.Status.Err
                    if most_recent_swarm_task.Status.Err is not None
                    else most_recent_swarm_task.Status.Message
                )

        return RegistryHealthCheckResult(
            status=deployment_status,
            reason=deployment_status_reason,
            id=registry.id,
        )

    @activity.defn
    async def save_registry_health_check_status(
        self, healthcheck: RegistryHealthCheckResult
    ):
        await BuildRegistry.objects.filter(pk=healthcheck.id).aupdate(
            health_status=healthcheck.status,
            healthcheck_message=healthcheck.reason or "",
        )


class MonitorComposeStackActivites:
    def __init__(self):
        self.docker = get_docker_client()

    @activity.defn
    async def run_stack_healthcheck(
        self, stack: ComposeStackSnapshot
    ) -> ComposeStackHealthcheckResult:
        services: List[DockerService] = self.docker.services.list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]},
            status=True,
        )
        statuses = await asyncio.gather(
            *[
                self._get_service_status(
                    service=service,
                    stack_name=stack.name,
                    stack_hash_prefix=stack.hash_prefix,
                )
                for service in services
            ]
        )

        service_statuses = {}
        for service_status in statuses:
            name = service_status.pop("name")
            service_statuses[name] = service_status

        return ComposeStackHealthcheckResult(
            id=stack.id,
            services={
                name: ComposeStackServiceStatusDto.from_dict(status)
                for name, status in service_statuses.items()
            },
        )

    async def _get_service_status(
        self,
        service: DockerService,
        stack_name: str,
        stack_hash_prefix: str,
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
                else ComposeStackServiceStatus.UNHEALTHY
            )
        else:
            # For regular services, healthy means running >= desired
            if running_replicas >= desired_replicas:
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
            .removeprefix(f"{stack_name}_")
            .removeprefix(f"{stack_hash_prefix}_")
        )
        return {
            "name": service_name,
            "mode": mode_type,
            "status": status,
            "desired_replicas": desired_replicas,
            "running_replicas": running_replicas,
            "updated_at": timezone.now().isoformat(),
            "tasks": [
                {
                    "status": task.state.value,
                    "message": task.message,
                    "exit_code": task.exit_code,
                }
                for task in tasks
            ],
        }

    @activity.defn
    async def save_stack_health_check_status(
        self, healthcheck: ComposeStackHealthcheckResult
    ):
        await ComposeStack.objects.filter(pk=healthcheck.id).aupdate(
            service_statuses={
                name: service.to_dict()
                for name, service in healthcheck.services.items()
            }
        )
