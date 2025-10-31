import math
from drf_spectacular.utils import extend_schema
from rest_framework import status, exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ServiceDetectedPortsResponseSerializer
from ..models import (
    Project,
    Service,
    Environment,
)
from datetime import timedelta


from django.core.cache import cache
from temporal.helpers import (
    get_service_open_port_key,
    get_swarm_service_name_for_deployment,
)
import docker
import docker.errors
from zane_api.utils import DockerSwarmTask


class ServiceDetectedPortsAPIView(APIView):
    serializer_class = ServiceDetectedPortsResponseSerializer

    @extend_schema(
        summary="Get detected service ports",
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug=Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = Service.objects.get(
                slug=service_slug, project=project, environment=environment
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        ports = []

        production_deployment = service.latest_production_deployment
        if production_deployment is not None:
            cache_key = get_service_open_port_key(production_deployment.hash)

            if cache.has_key(cache_key):
                ports = cache.get(cache_key)
            else:
                docker_client = docker.from_env()

                try:
                    swarm_service = docker_client.services.get(
                        get_swarm_service_name_for_deployment(
                            deployment_hash=production_deployment.hash,
                            project_id=project.id,
                            service_id=service.id,
                        )
                    )
                except docker.errors.NotFound:
                    pass  # no ports exposed if the service doesn't exists
                else:
                    task_list = swarm_service.tasks(
                        filters={
                            "label": f"deployment_hash={production_deployment.hash}",
                            "desired-state": "running",
                        }
                    )
                    most_recent_swarm_task = DockerSwarmTask.from_dict(
                        max(
                            task_list,
                            key=lambda task: task["Version"]["Index"],
                        )
                    )
                    if (
                        most_recent_swarm_task is not None
                        and most_recent_swarm_task.container_id is not None
                    ):
                        try:
                            container = docker_client.containers.get(
                                most_recent_swarm_task.container_id
                            )
                        except docker.errors.NotFound:
                            pass
                        else:
                            container_ports: dict[str, str | None] = container.attrs[
                                "NetworkSettings"
                            ]["Ports"]
                            for (
                                forwarded,
                                _external,
                            ) in (
                                container_ports.items()
                            ):  # in the format {'6379/tcp': '6380/tcp'}
                                port_number, protocol = forwarded.split("/")
                                ports.append(
                                    dict(
                                        port_number=int(port_number), protocol=protocol
                                    )
                                )

                            cache.set(
                                cache_key,
                                ports,
                                timeout=math.floor(timedelta(hours=24).total_seconds()),
                            )

        serializer = ServiceDetectedPortsResponseSerializer(ports)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
