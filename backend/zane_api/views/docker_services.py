import time

from django.db import transaction, IntegrityError
from django.db.models import Q, QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, inline_serializer
from faker import Faker
from rest_framework import status, exceptions
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE, ResourceConflict
from .serializers import (
    DockerServiceCreateRequestSerializer,
    DockerServiceDeploymentFilterSet,
    DockerServiceChangesRequestSerializer,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
)
from ..serializers import (
    DockerServiceDeploymentSerializer,
    DockerServiceSerializer,
    HealthCheckSerializer,
    VolumeSerializer,
    URLModelSerializer,
    PortConfigurationSerializer,
    DockerEnvVariableSerializer,
)
from ..tasks import delete_resources_for_docker_service


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
                try:
                    service = DockerRegistryService.objects.create(
                        slug=service_slug,
                        project=project,
                    )

                    service.network_alias = f"{service.slug}-{service.unprefixed_id}"
                    service.save()

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
                except IntegrityError:
                    raise ResourceConflict(
                        detail=f"A service with the slug `{service_slug}` already exists."
                    )

                response = DockerServiceSerializer(service)
                return Response(response.data, status=status.HTTP_201_CREATED)


class DockerServiceDeploymentChangesAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceChangesRequestSerializer,
        responses={
            200: DockerServiceSerializer,
        },
        operation_id="updateDeploymentChanges",
    )
    def patch(self, request: Request, project_slug: str, service_slug: str):
        project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        service: DockerRegistryService = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        form = DockerServiceChangesRequestSerializer(
            data=request.data, context={"service": service}
        )
        if form.is_valid(raise_exception=True):
            data = form.data
            new_changes: list[DockerDeploymentChange] = []
            for field, value in data.items():  # type: str, dict|list[dict]
                match field:
                    case "image" | "command" | "credentials":
                        change = DockerDeploymentChange(
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            field=field,
                            old_value=getattr(service, field),
                            new_value=value["new_value"],
                            service=service,
                        )
                        new_changes.append(change)
                    case "healthcheck":
                        change = DockerDeploymentChange(
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            field=field,
                            old_value=(
                                HealthCheckSerializer(service.healthcheck).data
                                if service.healthcheck is not None
                                else None
                            ),
                            new_value=value["new_value"],
                            service=service,
                        )
                        new_changes.append(change)
                    case "volumes":
                        for field_change in value:
                            old_value = None
                            if field_change["type"] in ["UPDATE", "DELETE"]:
                                old_value = VolumeSerializer(
                                    service.volumes.get(id=field_change["item_id"])
                                ).data
                            change = DockerDeploymentChange(
                                type=field_change["type"],
                                field=field,
                                old_value=old_value,
                                new_value=field_change["new_value"],
                                service=service,
                            )
                            new_changes.append(change)
                    case "urls":
                        for field_change in value:
                            old_value = None
                            if field_change["type"] in ["UPDATE", "DELETE"]:
                                old_value = URLModelSerializer(
                                    service.urls.get(id=field_change["item_id"])
                                ).data
                            change = DockerDeploymentChange(
                                type=field_change["type"],
                                field=field,
                                old_value=old_value,
                                new_value=field_change["new_value"],
                                service=service,
                            )
                            new_changes.append(change)
                    case "ports":
                        for field_change in value:
                            old_value = None
                            if field_change["type"] in ["UPDATE", "DELETE"]:
                                old_value = PortConfigurationSerializer(
                                    service.volumes.get(id=field_change["item_id"])
                                ).data
                            change = DockerDeploymentChange(
                                type=field_change["type"],
                                field=field,
                                old_value=old_value,
                                new_value=field_change["new_value"],
                                service=service,
                            )
                            new_changes.append(change)
                    case "env_variables":
                        for field_change in value:
                            old_value = None
                            if field_change["type"] in ["UPDATE", "DELETE"]:
                                old_value = DockerEnvVariableSerializer(
                                    service.env_variables.get(
                                        id=field_change["item_id"]
                                    )
                                ).data
                            change = DockerDeploymentChange(
                                type=field_change["type"],
                                field=field,
                                old_value=old_value,
                                new_value=field_change["new_value"],
                                service=service,
                            )
                            new_changes.append(change)

            service.add_changes(new_changes)

        response = DockerServiceSerializer(service)
        return Response(
            response.data,
        )


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
