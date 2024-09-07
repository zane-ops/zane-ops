import requests
from rest_framework import status
from temporalio import workflow, activity
from temporalio.exceptions import ApplicationError

from ..shared import HealthcheckDeploymentDetails, DeploymentHealthcheckResult

with workflow.unsafe.imports_passed_through():
    from django.conf import settings
    import docker
    import docker.errors
    from django import db
    from ...models import DockerDeployment, HealthCheck
    from ...utils import DockerSwarmTaskState, DockerSwarmTask

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
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=details.deployment.hash,
                    project_id=details.deployment.project_id,
                    service_id=details.deployment.service_id,
                )
            )
        except docker.errors.NotFound:
            raise ApplicationError(
                "Cannot run a healthcheck on an nonexistent deployment.",
                non_retryable=True,
            )
        else:
            healthcheck = details.healthcheck

            healthcheck_timeout = (
                healthcheck.timeout_seconds
                if healthcheck is not None
                else settings.DEFAULT_HEALTHCHECK_TIMEOUT
            )

            task_list = swarm_service.tasks(
                filters={"label": f"deployment_hash={details.deployment.hash}"}
            )
            if len(task_list) == 0:
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
                                full_url = f"{scheme}://{details.deployment.url + healthcheck.value}"
                                response = requests.get(
                                    full_url,
                                    headers={
                                        "Authorization": f"Token {details.auth_token}"
                                    },
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

                print(
                    f"Healtcheck for {details.deployment.hash=} | finished with {deployment_status=} ✅"
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
            deployment.status_reason = healthcheck_result.reason
            deployment.status = healthcheck_result.status
            await deployment.asave()
