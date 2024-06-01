import time
from typing import Any

from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q, QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    PolymorphicProxySerializer,
)
from faker import Faker
from rest_framework import status, exceptions
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE, ResourceConflict
from .helpers import compute_docker_service_snapshot_without_changes
from .serializers import (
    DockerServiceCreateRequestSerializer,
    DockerServiceDeploymentFilterSet,
    VolumeItemChangeSerializer,
    DockerCommandFieldChangeSerializer,
    DockerImageFieldChangeSerializer,
    URLItemChangeSerializer,
    EnvItemChangeSerializer,
    PortItemChangeSerializer,
    DockerCredentialsFieldChangeSerializer,
    HealthcheckFieldChangeSerializer,
    DockerDeploymentFieldChangeRequestSerializer,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
    HealthCheck,
    Volume,
    PortConfiguration,
    URL,
    DockerEnvVariable,
)
from ..serializers import (
    DockerServiceDeploymentSerializer,
    DockerServiceSerializer,
    HealthCheckSerializer,
    VolumeSerializer,
    URLModelSerializer,
    PortConfigurationSerializer,
    DockerEnvVariableSerializer,
    ErrorResponse409Serializer,
)
from ..tasks import delete_resources_for_docker_service, deploy_docker_service
from ..utils import strip_slash_if_exists


class CreateDockerServiceAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
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
                try:
                    healthcheck = data.get("healthcheck")
                    service = DockerRegistryService.objects.create(
                        slug=service_slug,
                        project=project,
                        image=data["image"],
                        command=data.get("command"),
                        credentials=docker_credentials,
                        healthcheck=(
                            HealthCheck.objects.create(
                                type=healthcheck["type"],
                                value=healthcheck["value"],
                                timeout_seconds=healthcheck["timeout_seconds"],
                                interval_seconds=healthcheck["interval_seconds"],
                            )
                            if healthcheck is not None
                            else None
                        ),
                    )

                    service.network_alias = f"{service.slug}-{service.unprefixed_id}"

                    initial_changes = [
                        DockerDeploymentChange(
                            field="image",
                            new_value=data["image"],
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            service=service,
                        )
                    ]

                    if docker_credentials is not None:
                        initial_changes.append(
                            DockerDeploymentChange(
                                field="credentials",
                                new_value=docker_credentials,
                                type=DockerDeploymentChange.ChangeType.UPDATE,
                                service=service,
                            )
                        )
                    DockerDeploymentChange.objects.bulk_create(initial_changes)
                    service.save()
                except IntegrityError:
                    raise ResourceConflict(
                        detail=f"A service with the slug `{service_slug}` already exists."
                    )

                # Create volumes if exists
                volumes_request = data.get("volumes", [])
                created_volumes = Volume.objects.bulk_create(
                    [
                        Volume(
                            name=volume.get("name", fake.slug().lower()),
                            container_path=volume["container_path"],
                            host_path=volume.get("host_path"),
                            mode=volume.get("mode"),
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
                        if port["host"] in http_ports:
                            has_at_least_one_http_port = True
                            break

                    if not has_at_least_one_http_port:
                        ports_from_request.append(
                            {
                                "host": 80,
                                "forwarded": 80,
                            }
                        )

                created_ports = PortConfiguration.objects.bulk_create(
                    [
                        PortConfiguration(
                            host=(
                                port["host"] if port["host"] not in http_ports else None
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
                        public_port = port["host"]
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
                            default_url = URL.create_default_url(service=service)
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
                    service=service, is_current_production=True
                )
                if len(service.urls.all()) > 0:
                    first_deployment.url = f"{project.slug}-{service_slug}-docker-{first_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}"
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


class RequestDockerServiceDeploymentChangesAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=PolymorphicProxySerializer(
            component_name="DeploymentChangeRequest",
            serializers=[
                URLItemChangeSerializer,
                VolumeItemChangeSerializer,
                EnvItemChangeSerializer,
                PortItemChangeSerializer,
                DockerCredentialsFieldChangeSerializer,
                DockerCommandFieldChangeSerializer,
                DockerImageFieldChangeSerializer,
                HealthcheckFieldChangeSerializer,
            ],
            resource_type_field_name="field",
        ),
        responses={
            200: DockerServiceSerializer,
        },
        operation_id="requestDeploymentChanges",
    )
    def put(self, request: Request, project_slug: str, service_slug: str):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service: DockerRegistryService = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        field_serializer_map = {
            "urls": URLItemChangeSerializer,
            "volumes": VolumeItemChangeSerializer,
            "env_variables": EnvItemChangeSerializer,
            "ports": PortItemChangeSerializer,
            "credentials": DockerCredentialsFieldChangeSerializer,
            "command": DockerCommandFieldChangeSerializer,
            "image": DockerImageFieldChangeSerializer,
            "healthcheck": HealthcheckFieldChangeSerializer,
        }

        request_serializer = DockerDeploymentFieldChangeRequestSerializer(
            data=request.data
        )
        if request_serializer.is_valid(raise_exception=True):
            form_serializer_class: type[Serializer] = field_serializer_map[
                request_serializer.data["field"]
            ]
            form = form_serializer_class(
                data=request.data, context={"service": service}
            )
            if form.is_valid(raise_exception=True):
                data = form.data
                field = data["field"]
                new_value = data.get("new_value")
                item_id = data.get("item_id")
                change_type = data.get("type")
                old_value: Any = None
                match field:
                    case "image" | "command" | "credentials":
                        old_value = getattr(service, field)
                    case "healthcheck":
                        old_value = (
                            HealthCheckSerializer(service.healthcheck).data
                            if service.healthcheck is not None
                            else None
                        )
                    case "volumes":
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = VolumeSerializer(
                                service.volumes.get(id=item_id)
                            ).data
                    case "urls":
                        old_value = None
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = URLModelSerializer(
                                service.urls.get(id=item_id)
                            ).data
                    case "ports":
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = PortConfigurationSerializer(
                                service.ports.get(id=item_id)
                            ).data
                    case "env_variables":
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = DockerEnvVariableSerializer(
                                service.env_variables.get(id=item_id)
                            ).data

                service.add_change(
                    DockerDeploymentChange(
                        type=change_type,
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                        service=service,
                    )
                )

                response = DockerServiceSerializer(service)
                return Response(response.data, status=status.HTTP_200_OK)


class CancelDockerServiceDeploymentChangesAPIView(APIView):
    @extend_schema(
        responses={
            409: ErrorResponse409Serializer,
            204: inline_serializer(
                name="CancelDockerServiveDeploymentChangesResponseSerializer", fields={}
            ),
        },
        operation_id="cancelDeploymentChanges",
    )
    def delete(
        self, request: Request, project_slug: str, service_slug: str, change_id: str
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service: DockerRegistryService = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )
        try:
            found_change = service.unapplied_changes.get(id=change_id)
        except DockerDeploymentChange.DoesNotExist:
            raise exceptions.NotFound(
                f"A pending change with id `{change_id}` does not exist in this service."
            )
        else:
            snapshot = compute_docker_service_snapshot_without_changes(
                service, change_id=change_id
            )
            if snapshot.image is None:
                raise ResourceConflict(
                    detail="Cannot delete this change because it would remove the image of the service."
                )

            if found_change.field == "ports" or found_change.field == "urls":
                is_healthcheck_path = (
                    snapshot.healthcheck is not None
                    and snapshot.healthcheck.type == "PATH"
                )
                service_is_not_exposed_to_http = (
                    len(snapshot.urls) == 0 and len(snapshot.http_ports) == 0
                )
                if is_healthcheck_path and service_is_not_exposed_to_http:
                    raise ResourceConflict(
                        f"Cannot delete this change because there is a healthcheck of type `path` attached to the service"
                        f" and the service is not exposed to the public through an URL or another HTTP port"
                    )

            found_change.delete()
            return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class ApplyDockerServiceDeploymentChangesAPIView(APIView):
    serializer_class = DockerServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=None,
        operation_id="applyDeploymentChanges",
    )
    def put(self, request: Request, project_slug: str, service_slug: str):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service: DockerRegistryService = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        new_deployment = DockerDeployment.objects.create(service=service)
        service.apply_pending_changes(deployment=new_deployment)

        if len(service.urls.all()) > 0:
            new_deployment.url = f"{project.slug}-{service_slug}-docker-{new_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}"
        new_deployment.service_snapshot = DockerServiceSerializer(service).data
        new_deployment.save()

        response = DockerServiceDeploymentSerializer(new_deployment)
        return Response(response.data, status=status.HTTP_200_OK)


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
            .prefetch_related("volumes", "ports", "urls", "env_variables")
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
