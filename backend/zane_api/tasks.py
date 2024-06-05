import json
from typing import Any

import billiard.einfo as e_info
import docker.errors
from celery import shared_task, Task
from django.conf import settings
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from .docker_operations import (
    expose_docker_service_to_http,
    create_docker_volume,
    create_service_from_docker_registry,
    create_project_resources,
    cleanup_project_resources,
    cleanup_docker_service_resources,
    unexpose_docker_service_from_http,
    get_updated_docker_service_deployment_status,
    scale_down_docker_service,
    expose_docker_service_deployment_to_http,
    create_resources_for_docker_service_deployment,
    get_updated_docker_deployment_status,
)
from .models import (
    DockerDeployment,
    PortConfiguration,
    Project,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
)
from .utils import cache_lock, LockAcquisitionError


def docker_service_deploy_failure(
    self: Task,
    exc: Exception,
    task_id: str,
    args: list[Any],
    kwargs: dict[str, str],
    einfo: e_info.ExceptionWithTraceback,
):
    print(f"ON DEPLOYMENT FAILURE {exc=}")
    deployment_hash = kwargs["deployment_hash"]
    deployment: DockerDeployment = DockerDeployment.objects.filter(
        hash=deployment_hash
    ).first()
    if deployment is not None:
        deployment.status = DockerDeployment.DeploymentStatus.FAILED
        deployment.status_reason = str(exc)
        scale_down_docker_service(deployment)
        deployment.save()


@shared_task(bind=True, on_failure=docker_service_deploy_failure)
def deploy_docker_service(
    self: Task, deployment_hash: str, service_id: str, auth_token: str
):
    lock_id = f"deploy_{service_id}"
    try:
        with cache_lock(lock_id):
            deployment: DockerDeployment | None = (
                DockerDeployment.objects.filter(hash=deployment_hash)
                .select_related("service", "service__project", "service__healthcheck")
                .prefetch_related(
                    "service__volumes",
                    "service__urls",
                    "service__ports",
                    "service__env_variables",
                )
                .first()
            )
            if deployment is None:
                raise DockerDeployment.DoesNotExist(
                    "Cannot execute a deploy a non existent deployment."
                )

            if deployment.status == DockerDeployment.DeploymentStatus.QUEUED:
                deployment.status = DockerDeployment.DeploymentStatus.PREPARING
                deployment.save()

            # TODO (#67) : send system logs when the resources are created
            service = deployment.service
            for volume in service.volumes.filter(host_path__isnull=True):
                create_docker_volume(volume, service=service)
            create_service_from_docker_registry(deployment)

            http_port: PortConfiguration = service.ports.filter(
                host__isnull=True
            ).first()
            if http_port is not None:
                expose_docker_service_deployment_to_http(deployment)

            deployment_status, deployment_status_reason = (
                get_updated_docker_service_deployment_status(
                    deployment,
                    auth_token=auth_token,
                    retry_if_not_healthy=True,
                )
            )
            if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY:
                deployment.status = deployment_status
                healthcheck = service.healthcheck

                deployment.monitor_task = PeriodicTask.objects.create(
                    interval=IntervalSchedule.objects.create(
                        every=(
                            healthcheck.interval_seconds
                            if healthcheck is not None
                            else settings.DEFAULT_HEALTHCHECK_INTERVAL
                        ),
                        period=IntervalSchedule.SECONDS,
                    ),
                    name=f"monitor deployment {deployment_hash}",
                    task="zane_api.tasks.monitor_docker_service_deployment",
                    kwargs=json.dumps(
                        {
                            "deployment_hash": deployment_hash,
                            "auth_token": auth_token,
                        }
                    ),
                )

                if http_port is not None:
                    expose_docker_service_to_http(deployment)
            else:
                deployment.status = DockerDeployment.DeploymentStatus.FAILED
                scale_down_docker_service(deployment)

            deployment.status_reason = deployment_status_reason
            deployment.save()
    except LockAcquisitionError as e:
        # Use the countdown from the exception for retrying
        self.retry(countdown=e.countdown, exc=e)
        return "retrying due to lock acquisistion error"


@shared_task(on_failure=docker_service_deploy_failure)
def deploy_docker_service_with_changes(
    deployment_hash: str, service_id: str, auth_token: str
):
    lock_id = f"deploy_{service_id}"
    try:
        with cache_lock(lock_id, timeout=settings.CELERY_TASK_TIME_LIMIT):
            deployment: DockerDeployment | None = (
                DockerDeployment.objects.filter(hash=deployment_hash)
                .select_related("service", "service__project", "service__healthcheck")
                .prefetch_related(
                    "service__volumes",
                    "service__urls",
                    "service__ports",
                    "service__env_variables",
                )
                .first()
            )
            if deployment is None:
                raise DockerDeployment.DoesNotExist(
                    "Cannot execute a deploy a non existent deployment."
                )
            if deployment.status == DockerDeployment.DeploymentStatus.QUEUED:
                deployment.status = DockerDeployment.DeploymentStatus.PREPARING
                deployment.save()

            # TODO (#67) : send system logs when the resources are created
            service = deployment.service
            for volume_change in deployment.changes.filter(
                field=DockerDeploymentChange.ChangeField.VOLUMES,
                type=DockerDeploymentChange.ChangeType.ADD,
            ):
                container_path = volume_change.new_value.get("container_path")
                corresponding_volume = service.volumes.get(
                    container_path=container_path
                )
                if corresponding_volume.host_path is None:
                    create_docker_volume(corresponding_volume, service=service)

            create_resources_for_docker_service_deployment(deployment)

            http_port: PortConfiguration = service.ports.filter(
                host__isnull=True
            ).first()
            if http_port is not None:
                expose_docker_service_deployment_to_http(deployment)

            deployment_status, deployment_status_reason = (
                get_updated_docker_deployment_status(
                    deployment,
                    auth_token=auth_token,
                    retry_if_not_healthy=True,
                )
            )

            if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY:
                deployment.status = deployment_status
                deployment.is_current_production = True
                healthcheck = service.healthcheck

                deployment.monitor_task = PeriodicTask.objects.create(
                    interval=IntervalSchedule.objects.create(
                        every=(
                            healthcheck.interval_seconds
                            if healthcheck is not None
                            else settings.DEFAULT_HEALTHCHECK_INTERVAL
                        ),
                        period=IntervalSchedule.SECONDS,
                    ),
                    name=f"monitor deployment {deployment_hash}",
                    task="zane_api.tasks.monitor_docker_service_deployment",
                    kwargs=json.dumps(
                        {
                            "deployment_hash": deployment_hash,
                            "auth_token": auth_token,
                        }
                    ),
                )

                if http_port is not None:
                    expose_docker_service_to_http(deployment)
            else:
                deployment.status = DockerDeployment.DeploymentStatus.FAILED
                scale_down_docker_service(deployment)

            deployment.status_reason = deployment_status_reason
            deployment.save()
    except LockAcquisitionError:
        return "will retry after the current one is finished"


@shared_task(
    autoretry_for=(docker.errors.APIError,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def create_docker_resources_for_project(project_slug: str):
    create_project_resources(project=Project.objects.get(slug=project_slug))


@shared_task(
    autoretry_for=(docker.errors.APIError, TimeoutError),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def delete_docker_resources_for_project(archived_project_id: int):
    archived_project = ArchivedProject.objects.get(pk=archived_project_id)

    archived_docker_services = (
        ArchivedDockerService.objects.filter(project=archived_project)
        .select_related("project")
        .prefetch_related("volumes", "urls")
    )

    for docker_service in archived_docker_services:
        cleanup_docker_service_resources(docker_service)
        unexpose_docker_service_from_http(docker_service)

    cleanup_project_resources(archived_project)


@shared_task(
    autoretry_for=(docker.errors.APIError, TimeoutError),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def delete_resources_for_docker_service(archived_service_id: id):
    archived_service = (
        ArchivedDockerService.objects.filter(id=archived_service_id)
        .select_related("project")
        .prefetch_related("volumes", "urls", "deployment_urls")
    ).first()
    if archived_service is None:
        raise ArchivedDockerService.DoesNotExist(
            f"Cannot execute a ressource deletion a non existent archived service with id={archived_service_id}."
        )
    unexpose_docker_service_from_http(archived_service)
    cleanup_docker_service_resources(archived_service)


@shared_task
def monitor_docker_service_deployment(deployment_hash: str, auth_token: str):
    deployment: DockerDeployment | None = (
        DockerDeployment.objects.filter(hash=deployment_hash)
        .select_related("service", "service__project")
        .prefetch_related(
            "service__volumes",
            "service__urls",
            "service__ports",
            "service__env_variables",
            "service__healthcheck",
        )
        .first()
    )

    if (
        deployment is not None
        and deployment.status != DockerDeployment.DeploymentStatus.REMOVED
    ):
        try:
            deployment_status, deployment_status_reason = (
                get_updated_docker_deployment_status(deployment, auth_token)
            )
            deployment.status = deployment_status
            deployment.status_reason = deployment_status_reason
        except TimeoutError as e:
            deployment.status = DockerDeployment.DeploymentStatus.UNHEALTHY
            deployment.status_reason = str(e)
        finally:
            deployment.save()
