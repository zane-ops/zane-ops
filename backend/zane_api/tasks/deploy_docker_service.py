from celery import shared_task


@shared_task
def deploy_docker_service(service_slug: str, project_slug: str):
    return
