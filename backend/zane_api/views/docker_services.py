import time

from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q, QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, inline_serializer
from faker import Faker
from rest_framework import status, exceptions
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE, ResourceConflict
from .serializers import (
    DockerServiceCreateRequestSerializer,
    DockerServiceDeploymentFilterSet,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    Volume,
    PortConfiguration,
    URL,
    DockerEnvVariable,
    ArchivedProject,
    ArchivedDockerService,
    HealthCheck,
)
from ..serializers import DockerServiceDeploymentSerializer, DockerServiceSerializer
from ..tasks import deploy_docker_service, delete_resources_for_docker_service
from ..utils import strip_slash_if_exists


class CreateDockerServiceAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            201: DockerServiceSerializer,
        },
        operation_id="createDockerService",
    )
    @transaction.atomic()
    def post(self, request: Request, project_slug: str):
        try:
            project = Project.objects.get(slug=project_slug, owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                f"A project with the slug `{project_slug}` does not exist"
            )
        else:
            form = DockerServiceCreateRequestSerializer(data=request.data)
            if form.is_valid(raise_exception=True):
                data = form.data

                # Create service in DB
                docker_credentials: dict | None = data.get("credentials")
                fake = Faker()
                Faker.seed(time.monotonic())
                service_slug = data.get("slug", fake.slug()).lower()
                docker_image_tag = "latest"
                try:
                    docker_image = data["image"]
                    docker_image_parts = docker_image.split(":", 1)
                    if len(docker_image_parts) == 2:
                        docker_image, docker_image_tag = docker_image_parts

                    healthcheck = data.get("healthcheck")
                    service = DockerRegistryService.objects.create(
                        slug=service_slug,
                        project=project,
                        image_repository=docker_image,
                        command=data.get("command"),
                        docker_credentials_username=(
                            docker_credentials.get("username")
                            if docker_credentials is not None
                            else None
                        ),
                        docker_credentials_password=(
                            docker_credentials.get("password")
                            if docker_credentials is not None
                            else None
                        ),
                        healthcheck=(
                            HealthCheck.objects.create(
                                type=healthcheck["type"].upper(),
                                value=healthcheck["value"],
                                timeout_seconds=healthcheck["timeout_seconds"],
                                interval_seconds=healthcheck["interval_seconds"],
                            )
                            if healthcheck is not None
                            else None
                        ),
                    )

                    service.network_alias = f"{service.slug}-{service.unprefixed_id}"
                    service.save()
                except IntegrityError:
                    raise ResourceConflict(
                        detail=f"A service with the slug `{service_slug}` already exists."
                    )

                # Create volumes if exists
                volumes_request = data.get("volumes", [])
                volume_mode_map = {
                    "rw": Volume.VolumeMode.READ_WRITE,
                    "ro": Volume.VolumeMode.READ_ONLY,
                }
                created_volumes = Volume.objects.bulk_create(
                    [
                        Volume(
                            name=volume.get("name", fake.slug().lower()),
                            container_path=volume["mount_path"],
                            host_path=volume.get("host_path"),
                            mode=volume_mode_map[volume.get("mode")],
                        )
                        for volume in volumes_request
                    ]
                )

                service.volumes.add(*created_volumes)

                # create ports configuration
                service_urls_from_request = data.get("urls", [])
                ports_from_request = data.get("ports", [])
                http_ports = [80, 443]

                if len(service_urls_from_request) > 0:
                    has_at_least_one_http_port = False
                    for port in ports_from_request:
                        if port["public"] in http_ports:
                            has_at_least_one_http_port = True
                            break

                    if not has_at_least_one_http_port:
                        ports_from_request.append(
                            {
                                "public": 80,
                                "forwarded": 80,
                            }
                        )

                created_ports = PortConfiguration.objects.bulk_create(
                    [
                        PortConfiguration(
                            host=(
                                port["public"]
                                if port["public"] not in http_ports
                                else None
                            ),
                            forwarded=port["forwarded"],
                        )
                        for port in ports_from_request
                    ]
                )

                service.ports.add(*created_ports)

                # Create urls to route the service to
                can_create_urls = len(service_urls_from_request) > 0
                if not can_create_urls:
                    for port in ports_from_request:
                        public_port = port["public"]
                        if public_port in http_ports:
                            can_create_urls = True
                            break

                if can_create_urls:
                    if len(service_urls_from_request) == 0:
                        existing_urls = URL.objects.filter(
                            domain=f"{project.slug}-{service_slug}.{settings.ROOT_DOMAIN}",
                            base_path="/",
                        ).first()
                        if existing_urls is None:
                            default_url = URL.objects.create(
                                domain=f"{project.slug}-{service_slug}.{settings.ROOT_DOMAIN}",
                                base_path="/",
                            )
                        else:
                            default_url = URL.objects.create(
                                domain=f"{project.slug}-{service_slug}-{fake.slug()}.{settings.ROOT_DOMAIN}",
                                base_path="/",
                            )
                        service.urls.add(default_url)
                    else:
                        urls_to_create: list[URL] = []

                        for url in service_urls_from_request:
                            base_path = (
                                "/"
                                if url["base_path"] == "/"
                                else strip_slash_if_exists(
                                    url["base_path"],
                                    strip_end=True,
                                    strip_start=False,
                                )
                            )
                            urls_to_create.append(
                                URL(
                                    domain=url["domain"],
                                    base_path=base_path,
                                    strip_prefix=url["strip_prefix"],
                                )
                            )

                        created_urls = URL.objects.bulk_create(urls_to_create)
                        service.urls.add(*created_urls)

                # Create first deployment
                first_deployment = DockerDeployment.objects.create(
                    service=service, image_tag=docker_image_tag
                )
                if len(service.urls.all()) > 0:
                    first_deployment.url = f"{project.slug}-{service_slug}-{first_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}"
                    first_deployment.save()

                # Create envs if exists
                envs_from_request: dict[str, str] = data.get("env", {})

                DockerEnvVariable.objects.bulk_create(
                    [
                        DockerEnvVariable(key=key, value=value, service=service)
                        for key, value in envs_from_request.items()
                    ]
                )

                token = Token.objects.get(user=request.user)
                # Run celery deployment task
                transaction.on_commit(
                    lambda: deploy_docker_service.apply_async(
                        kwargs=dict(
                            deployment_hash=first_deployment.hash,
                            service_id=service.id,
                            auth_token=token.key,
                        ),
                        task_id=first_deployment.task_id,
                    )
                )

                response = DockerServiceSerializer(service)
                return Response(response.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            200: DockerServiceSerializer,
        },
        operation_id="updateDockerService",
    )
    def put(self, request: Request, project_slug: str, service_slug: str):
        return Response()


class GetDockerServiceAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        operation_id="getDockerService",
    )
    def get(self, request: Request, project_slug: str, service_slug: str):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        response = DockerServiceSerializer(service)
        return Response(response.data, status=status.HTTP_200_OK)


class DockerServiceDeploymentsAPIView(ListAPIView):
    serializer_class = DockerServiceDeploymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DockerServiceDeploymentFilterSet
    queryset = (
        DockerDeployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    def get_queryset(self) -> QuerySet[DockerDeployment]:
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except DockerRegistryService.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        return (
            DockerDeployment.objects.filter(service=service)
            .select_related("service", "is_redeploy_of")
            .order_by("-created_at")
        )


class DockerServiceDeploymentSingleAPIView(RetrieveAPIView):
    serializer_class = DockerServiceDeploymentSerializer
    lookup_url_kwarg = "deployment_hash"  # This corresponds to the URL configuration
    queryset = (
        DockerDeployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_object`

    def get_object(self):
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        deployment_hash = self.kwargs["deployment_hash"]

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            deployment: DockerDeployment | None = (
                DockerDeployment.objects.filter(service=service, hash=deployment_hash)
                .select_related("service", "is_redeploy_of")
                .first()
            )
            if deployment is None:
                raise DockerDeployment.DoesNotExist("")
            return deployment
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except DockerRegistryService.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )
        except DockerDeployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )


class ArchiveDockerServiceAPIView(APIView):
    @extend_schema(
        responses={
            204: inline_serializer(
                name="AchiveDockerServiveResponseSerializer", fields={}
            ),
        },
        operation_id="archiveDockerService",
    )
    @transaction.atomic()
    def delete(self, request: Request, project_slug: str, service_slug: str):
        project = (
            Project.objects.filter(
                slug=project_slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )

        service: DockerRegistryService = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        archived_project = (
            project.archived_version if hasattr(project, "archived_version") else None
        )
        if archived_project is None:
            archived_project = ArchivedProject.create_from_project(project)

        archived_service = ArchivedDockerService.create_from_service(
            service, archived_project
        )

        archive_task_id = service.archive_task_id
        service.delete_resources()
        service.delete()

        transaction.on_commit(
            lambda: delete_resources_for_docker_service.apply_async(
                kwargs=dict(archived_service_id=archived_service.id),
                task_id=archive_task_id,
            )
        )

        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)
