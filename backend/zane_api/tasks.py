import json
from typing import Any

import docker.errors
from billiard.einfo import ExceptionWithTraceback
from celery import shared_task, Task
from django.db import transaction
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
)
from .models import (
    DockerDeployment,
    PortConfiguration,
    Project,
    ArchivedProject,
    ArchivedDockerService,
)
from .utils import cache_lock, LockAcquisitionError


def docker_service_deploy_failure(
    self: Task,
    exc: Exception,
    task_id: str,
    args: list[Any],
    kwargs: dict[str, str],
    einfo: ExceptionWithTraceback,
):
    print(f"ON DEPLOYMENT FAILURE {exc=}")
    with transaction.atomic():
        deployment_hash = kwargs["deployment_hash"]
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            hash=deployment_hash
        ).first()
        if deployment is not None:
            deployment.deployment_status = DockerDeployment.DeploymentStatus.FAILED
            deployment.deployment_status_reason = str(exc)
            scale_down_docker_service(deployment)
            deployment.save()


@shared_task(bind=True, on_failure=docker_service_deploy_failure)
def deploy_docker_service(self: Task, deployment_hash: str, service_id: str):
    lock_id = f"deploy_{service_id}"
    try:
        with cache_lock(lock_id):
            with transaction.atomic():
                deployment: DockerDeployment | None = (
                    DockerDeployment.objects.filter(hash=deployment_hash)
                    .select_related(
                        "service", "service__project", "service__healthcheck"
                    )
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

                if (
                    deployment.deployment_status
                    == DockerDeployment.DeploymentStatus.QUEUED
                ):
                    deployment.deployment_status = (
                        DockerDeployment.DeploymentStatus.PREPARING
                    )
                    deployment.save()

                # TODO (#67) : send system logs when the resources are created
                service = deployment.service
                for volume in service.volumes.all():
                    create_docker_volume(volume, service=service)
                create_service_from_docker_registry(deployment)

                http_port: PortConfiguration = service.ports.filter(
                    host__isnull=True
                ).first()
                if http_port is not None:
                    expose_docker_service_to_http(deployment)

                deployment_status, deployment_status_reason = (
                    get_updated_docker_service_deployment_status(
                        deployment, wait_for_healthy=True
                    )
                )
                if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY:
                    deployment.deployment_status = deployment_status
                    healthcheck = service.healthcheck

                    deployment.monitor_task = PeriodicTask.objects.create(
                        interval=IntervalSchedule.objects.create(
                            every=(
                                healthcheck.interval_seconds
                                if healthcheck is not None
                                else 30
                            ),
                            period=IntervalSchedule.SECONDS,
                        ),
                        name=f"monitor deployment {deployment_hash}",
                        task="zane_api.tasks.monitor_docker_service_deployment",
                        kwargs=json.dumps({"deployment_hash": deployment_hash}),
                    )
                else:
                    deployment.deployment_status = (
                        DockerDeployment.DeploymentStatus.FAILED
                    )
                    scale_down_docker_service(deployment)

                deployment.deployment_status_reason = deployment_status_reason
                deployment.save()
    except LockAcquisitionError as e:
        # Use the countdown from the exception for retrying
        self.retry(countdown=e.countdown, exc=e)
        return "retrying due to lock acquisistion error"
    except Exception as exc:
        # Handle other exceptions potentially by re-raising or logging
        raise exc


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
    with transaction.atomic():
        archived_service = (
            ArchivedDockerService.objects.filter(id=archived_service_id)
            .select_related("project")
            .prefetch_related("volumes", "urls", "deployment_urls")
        ).first()
        if archived_service is None:
            raise ArchivedDockerService.DoesNotExist(
                f"Cannot execute a ressource deletion a non existent archived service with id={archived_service_id}."
            )
        cleanup_docker_service_resources(archived_service)
        unexpose_docker_service_from_http(archived_service)


@shared_task
def monitor_docker_service_deployment(deployment_hash: str):
    with transaction.atomic():
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
            and deployment.deployment_status
            != DockerDeployment.DeploymentStatus.OFFLINE
        ):
            deployment_status, deployment_status_reason = (
                get_updated_docker_service_deployment_status(deployment)
            )
            deployment.deployment_status = deployment_status
            deployment.deployment_status_reason = deployment_status_reason
            deployment.save()
