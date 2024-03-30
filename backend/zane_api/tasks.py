import docker.errors
from celery import shared_task

from .docker_operations import (
    expose_docker_service_to_http,
    create_docker_volume,
    create_service_from_docker_registry,
    create_project_resources,
    cleanup_project_resources,
    cleanup_docker_service_resources,
)
from .models import (
    DockerDeployment,
    PortConfiguration,
    Project,
    ArchivedProject,
    ArchivedDockerService,
)


@shared_task
def deploy_docker_service(deployment_hash: str):
    deployment: DockerDeployment | None = (
        DockerDeployment.objects.filter(hash=deployment_hash)
        .select_related("service", "service__project")
        .prefetch_related(
            "service__volumes",
            "service__urls",
            "service__ports",
            "service__env_variables",
        )
        .first()
    )
    if deployment is None:
        raise Exception("Cannot execute a deploy a non existent deployment.")

    service = deployment.service
    for volume in service.volumes.all():
        create_docker_volume(volume, service=service)
    create_service_from_docker_registry(service)

    http_port: PortConfiguration = service.ports.filter(host__isnull=True).first()
    if http_port is not None:
        expose_docker_service_to_http(service)


@shared_task(
    autoretry_for=(docker.errors.APIError,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def create_docker_resources_for_project(project_slug: str):
    create_project_resources(project=Project.objects.get(slug=project_slug))


@shared_task(
    autoretry_for=(docker.errors.APIError,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def delete_docker_resources_for_project(archived_project_id: int):
    archived_project = ArchivedProject.objects.get(pk=archived_project_id)
    cleanup_project_resources(archived_project)


@shared_task(
    autoretry_for=(docker.errors.APIError,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
)
def delete_resources_for_docker_service(archived_service_id: id):
    archived_service = (
        ArchivedDockerService.objects.filter(id=archived_service_id)
        .select_related('project')
        .prefetch_related(
            "volumes"
        )
    ).first()
    if archived_service is None:
        raise Exception(f"Cannot execute a deploy a non existent archived service with id={archived_service_id}.")
    cleanup_docker_service_resources(archived_service)
