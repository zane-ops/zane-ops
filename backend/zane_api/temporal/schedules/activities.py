from datetime import timedelta
import requests
from rest_framework import status
from temporalio import workflow, activity
from temporalio.exceptions import ApplicationError


from ..shared import (
    CleanupResult,
    HealthcheckDeploymentDetails,
    DeploymentHealthcheckResult,
    ServiceMetricsResult,
    SimpleDeploymentDetails,
)

with workflow.unsafe.imports_passed_through():
    from django.conf import settings
    from django.utils import timezone
    import docker
    import docker.errors
    from django import db
    from ...models import DockerDeployment, HealthCheck, ServiceMetrics
    from ...utils import (
        DockerSwarmTaskState,
        DockerSwarmTask,
        Colors,
        escape_ansi,
        excerpt,
    )
    from search.loki_client import LokiSearchClient
    from search.dtos import RuntimeLogDto, RuntimeLogLevel, RuntimeLogSource

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


class MonitorDockerDeploymentActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def monitor_close_faulty_db_connections(self):
        """
        This is to fix a bug we encountered when the worker hadn't run any job for a long time,
        after that time, Django lost the DB connections, what is needed is to close the connection
        so that Django can recreate the connection.
        https://stackoverflow.com/questions/31504591/interfaceerror-connection-already-closed-using-django-celery-scrapy
        """
        for conn in db.connections.all():
            conn.close_if_unusable_or_obsolete()

    @activity.defn
    async def run_deployment_monitor_healthcheck(
        self,
        details: HealthcheckDeploymentDetails,
    ) -> tuple[DockerDeployment.DeploymentStatus, str]:
        try:
            docker_deployment = await DockerDeployment.objects.aget(
                hash=details.deployment.hash,
            )

            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=details.deployment.hash,
                    project_id=details.deployment.project_id,
                    service_id=details.deployment.service_id,
                )
            )
        except (docker.errors.NotFound, DockerDeployment.DoesNotExist):
            raise ApplicationError(
                "Cannot run a healthcheck on an nonexistent deployment.",
                non_retryable=True,
            )
        else:
            if docker_deployment.status == DockerDeployment.DeploymentStatus.SLEEPING:
                return (
                    DockerDeployment.DeploymentStatus.SLEEPING,
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
                deployment_status = DockerDeployment.DeploymentStatus.UNHEALTHY
                deployment_status_reason = "Error: The service is down, did you manually scale down the service ?"
            else:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                state_matrix = {
                    DockerSwarmTaskState.NEW: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PENDING: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ASSIGNED: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ACCEPTED: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.READY: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PREPARING: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.STARTING: DockerDeployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.RUNNING: DockerDeployment.DeploymentStatus.HEALTHY,
                    DockerSwarmTaskState.COMPLETE: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.FAILED: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.SHUTDOWN: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.REJECTED: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.ORPHANED: DockerDeployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.REMOVE: DockerDeployment.DeploymentStatus.UNHEALTHY,
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
                    deployment_status == DockerDeployment.DeploymentStatus.STARTING
                    and len(all_tasks) > 1
                ):
                    deployment_status = DockerDeployment.DeploymentStatus.RESTARTING
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
                                    timeout=healthcheck_timeout,
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

            status_color = (
                Colors.GREEN
                if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY
                else Colors.RED
            )

            print(
                f"Healthcheck for {details.deployment.hash=} | finished with {deployment_status=} 🏁"
            )

            unhealthy = deployment_status != DockerDeployment.DeploymentStatus.HEALTHY

            if unhealthy:
                if deployment_status == DockerDeployment.DeploymentStatus.UNHEALTHY:
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
    async def save_deployment_status(
        self, healthcheck_result: DeploymentHealthcheckResult
    ):
        try:
            deployment: DockerDeployment = await DockerDeployment.objects.aget(
                hash=healthcheck_result.deployment_hash
            )
        except DockerDeployment.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent deployment.",
                non_retryable=True,
            )
        else:
            if (
                deployment.status != DockerDeployment.DeploymentStatus.SLEEPING
                and deployment.is_current_production
            ):
                deployment.status_reason = healthcheck_result.reason
                deployment.status = healthcheck_result.status
                await deployment.asave()


class DockerDeploymentStatsActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def get_deployment_stats(
        self, details: SimpleDeploymentDetails
    ) -> ServiceMetricsResult | None:
        try:
            docker_deployment = await DockerDeployment.objects.aget(
                hash=details.hash,
            )
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=details.hash,
                    project_id=details.project_id,
                    service_id=details.service_id,
                )
            )
        except (docker.errors.NotFound, DockerDeployment.DoesNotExist):
            raise ApplicationError(
                "Cannot run a healthcheck on an nonexistent deployment.",
                non_retryable=True,
            )
        else:
            if docker_deployment.status == DockerDeployment.DeploymentStatus.SLEEPING:
                return None

            task_list = swarm_service.tasks(
                filters={"label": f"deployment_hash={details.hash}"}
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
            await DockerDeployment.objects.filter(
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
