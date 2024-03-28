from celery import shared_task

from .docker_operations import (
    expose_docker_service_to_http,
    create_docker_volume,
    create_service_from_docker_registry,
)
from .models import DockerDeployment, PortConfiguration


@shared_task
def deploy_docker_service(deployment_hash: str):
    deployment: DockerDeployment | None = (
        DockerDeployment.objects.filter(hash=deployment_hash)
        .select_related("service", "service__project")
        .prefetch_related("service__volumes", "service__urls", "service__ports")
        .first()
    )
    if deployment is None:
        raise Exception("Cannot execute a deploy a non existent deployment.")

    service = deployment.service
    for volume in service.volumes.all():
        create_docker_volume(volume)
    create_service_from_docker_registry(service, deployment)

    http_port: PortConfiguration = service.ports.filter(host__isnull=True).first()
    if http_port is not None:
        expose_docker_service_to_http(service)
