import json
from typing import Any

import billiard.einfo as e_info
import docker.errors
from celery import shared_task, Task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from .docker_operations import (
    expose_docker_service_to_http,
    create_docker_volume,
    create_project_resources,
    cleanup_project_resources,
    cleanup_docker_service_resources,
    unexpose_docker_service_from_http,
    expose_docker_service_deployment_to_http,
    create_resources_for_docker_service_deployment,
    get_updated_docker_deployment_status,
    delete_docker_volume,
    scale_down_and_remove_docker_service_deployment,
    unexpose_docker_deployment_from_http,
    apply_deleted_urls_changes,
    scale_down_service_deployment,
    scale_back_service_deployment,
)
from .models import (
    DockerDeployment,
    PortConfiguration,
    Project,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
    SimpleLog,
)
from .utils import cache_lock, LockAcquisitionError, find_item_in_list
from .views.helpers import URLDto


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
    deployment: DockerDeployment = (
        DockerDeployment.objects.filter(hash=deployment_hash)
        .select_related("service")
        .first()
    )

    if deployment is not None:
        deployment.status = DockerDeployment.DeploymentStatus.FAILED
        deployment.status_reason = str(exc)

        latest_production_deploy = deployment.service.latest_production_deployment
        if (
            latest_production_deploy is not None
            and latest_production_deploy.id != deployment.id
        ):
            scale_back_service_deployment(latest_production_deploy)

        scale_down_and_remove_docker_service_deployment(deployment)

        if deployment.service.deployments.count() == 1:
            deployment.is_current_production = True

        deployment.finished_at = timezone.now()
        deployment.save()

        # delete all monitor tasks that might have been created in the meantime
        PeriodicTask.objects.filter(name=deployment.monitor_task_name).delete()

        service = deployment.service
        next_deployment = service.last_queued_deployment
        if next_deployment is not None:
            deploy_docker_service_with_changes.apply_async(
                kwargs=dict(
                    deployment_hash=next_deployment.hash,
                    service_id=service.id,
                    auth_token=kwargs["auth_token"],
                ),
                task_id=next_deployment.workflow_id,
            )


@shared_task(
    autoretry_for=(TimeoutError,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
    on_failure=docker_service_deploy_failure,
)
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
                deployment.started_at = timezone.now()
                deployment.save()

            # TODO (#67) : send system logs when the resources are created
            service = deployment.service
            latest_production_deploy = service.latest_production_deployment
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

            if (
                service.volumes.count() > 0
                or service.ports.filter(host__isnull=False).count() > 0
            ) and latest_production_deploy is not None:
                scale_down_service_deployment(latest_production_deploy)

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
                    name=deployment.monitor_task_name,
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
                if service.deployments.count() == 1:
                    deployment.is_current_production = True
                deployment.status = DockerDeployment.DeploymentStatus.FAILED

                if latest_production_deploy is not None:
                    scale_back_service_deployment(latest_production_deploy)
                scale_down_and_remove_docker_service_deployment(deployment)

            deployment.status_reason = deployment_status_reason
            deployment.finished_at = timezone.now()
            deployment.save()
    except LockAcquisitionError:
        return "will retry after the current one is finished"
    else:
        if (
            latest_production_deploy is not None
            and deployment.status == DockerDeployment.DeploymentStatus.HEALTHY
        ):
            service.deployments.filter(~Q(hash=deployment_hash)).update(
                is_current_production=False
            )
            cleanup_docker_resources_for_deployment.apply_async(
                kwargs=dict(
                    old_deployment_hash=latest_production_deploy.hash,
                    new_deployment_hash=deployment.hash,
                )
            )

        next_deployment = service.last_queued_deployment
        if next_deployment is not None:
            deploy_docker_service_with_changes.apply_async(
                kwargs=dict(
                    deployment_hash=next_deployment.hash,
                    service_id=service.id,
                    auth_token=auth_token,
                ),
                task_id=next_deployment.workflow_id,
            )


@shared_task(
    autoretry_for=(docker.errors.APIError, TimeoutError),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def cleanup_docker_resources_for_deployment(
    old_deployment_hash: str, new_deployment_hash: str
):
    old_deployment: DockerDeployment = DockerDeployment.objects.get(
        hash=old_deployment_hash
    )
    new_deployment: DockerDeployment = DockerDeployment.objects.get(
        hash=new_deployment_hash
    )

    unexpose_docker_deployment_from_http(old_deployment)
    scale_down_and_remove_docker_service_deployment(
        old_deployment, wait_service_down=True
    )

    for volume_change in new_deployment.changes.filter(
        field=DockerDeploymentChange.ChangeField.VOLUMES,
        type=DockerDeploymentChange.ChangeType.DELETE,
    ):
        delete_docker_volume(volume_change.item_id)

    urls_to_delete = list(
        map(
            lambda change: URLDto.from_dict(change.old_value),
            new_deployment.changes.filter(
                Q(field=DockerDeploymentChange.ChangeField.URLS)
                & Q(old_value__isnull=False)
                & (
                    Q(type=DockerDeploymentChange.ChangeType.DELETE)
                    | Q(type=DockerDeploymentChange.ChangeType.UPDATE)
                ),
            ),
        )
    )

    # This is a fix that check that the URL hasn't been re-added again
    # Because since we add new URLs before deleting old urls
    # it might delete the newly added URL
    existing_urls = new_deployment.service.urls.filter(
        Q(domain__in=[url.domain for url in urls_to_delete])
        & Q(base_path__in=[url.base_path for url in urls_to_delete])
    )
    for url in existing_urls:
        existing_url = find_item_in_list(
            lambda item: item.domain == url.domain and item.base_path == url.base_path,
            urls_to_delete,
        )
        if existing_url is not None:
            urls_to_delete.remove(existing_url)

    apply_deleted_urls_changes(urls_to_delete)

    old_deployment.status = DockerDeployment.DeploymentStatus.REMOVED
    old_deployment.save()


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

    for archived_service in archived_docker_services:
        unexpose_docker_service_from_http(archived_service)
        cleanup_docker_service_resources(archived_service)

    cleanup_project_resources(archived_project)


@shared_task(
    autoretry_for=(docker.errors.APIError, TimeoutError),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def delete_resources_for_docker_service(archived_service_id: id):
    archived_service: ArchivedDockerService = (
        ArchivedDockerService.objects.filter(id=archived_service_id)
        .select_related("project")
        .prefetch_related("volumes", "urls")
    ).first()
    if archived_service is None:
        raise ArchivedDockerService.DoesNotExist(
            f"Cannot execute a ressource deletion a non existent archived service with id={archived_service_id}."
        )
    unexpose_docker_service_from_http(archived_service)
    cleanup_docker_service_resources(archived_service)
    SimpleLog.objects.filter(service_id=archived_service.original_id).delete()


@shared_task
def monitor_docker_service_deployment(deployment_hash: str, auth_token: str):
    lock_id = f"monitor_{deployment_hash}"
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
        and deployment.status != DockerDeployment.DeploymentStatus.FAILED
    ):
        try:
            healthcheck = deployment.service.healthcheck
            timeout_margin = 5  # seconds
            monitor_timeout = (
                healthcheck.timeout_seconds
                if healthcheck is not None
                else settings.DEFAULT_HEALTHCHECK_TIMEOUT
            ) + timeout_margin
            with cache_lock(lock_id, timeout=monitor_timeout):
                deployment_status, deployment_status_reason = (
                    get_updated_docker_deployment_status(deployment, auth_token)
                )
                deployment.status = deployment_status
                deployment.status_reason = deployment_status_reason
        except LockAcquisitionError:
            return "Ignored, another monitor task is already running and hasn't finished yet"
        except TimeoutError as e:
            deployment.status = DockerDeployment.DeploymentStatus.UNHEALTHY
            deployment.status_reason = str(e)
        finally:
            deployment.save()
