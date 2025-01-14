import time
from typing import Any

import django.db.transaction as transaction
from django.conf import settings
from django.db import IntegrityError
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

from search.client import SearchClient
from search.serializers import RuntimeLogsSearchSerializer

from .base import (
    EMPTY_RESPONSE,
    ResourceConflict,
    EMPTY_PAGINATED_RESPONSE,
    EMPTY_CURSOR_RESPONSE,
)
from .helpers import (
    compute_docker_service_snapshot_without_changes,
    compute_docker_changes_from_snapshots,
)
from .serializers import (
    DeploymentLogsQuerySerializer,
    DockerServiceCreateRequestSerializer,
    DockerServiceDeploymentFilterSet,
    DockerServiceUpdateRequestSerializer,
    DockerSourceFieldChangeSerializer,
    VolumeItemChangeSerializer,
    DockerCommandFieldChangeSerializer,
    URLItemChangeSerializer,
    EnvItemChangeSerializer,
    PortItemChangeSerializer,
    HealthcheckFieldChangeSerializer,
    DockerDeploymentFieldChangeRequestSerializer,
    DeploymentListPagination,
    DeploymentLogsPagination,
    DeploymentHttpLogsFilterSet,
    DockerServiceDeployRequestSerializer,
    ResourceLimitChangeSerializer,
)
from ..dtos import URLDto, VolumeDto
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
    HttpLog,
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
    HttpLogSerializer,
)
from ..temporal import (
    start_workflow,
    DeployDockerServiceWorkflow,
    DockerDeploymentDetails,
    ArchivedServiceDetails,
    ArchiveDockerServiceWorkflow,
    SimpleDeploymentDetails,
    ToggleDockerServiceWorkflow,
    workflow_signal,
    CancelDeploymentSignalInput,
)
from ..utils import generate_random_chars


class CreateDockerServiceAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            201: DockerServiceSerializer,
        },
        operation_id="createDockerService",
        summary="Create a docker service",
        description="Create a service from a docker image.",
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
                        deploy_token=generate_random_chars(20),
                    )

                    service.network_alias = f"zn-{service.slug}-{service.unprefixed_id}"

                    source_data = {
                        "image": data["image"],
                    }
                    if docker_credentials is not None and (
                        len(docker_credentials.get("username", "")) > 0
                        or len(docker_credentials.get("password", "")) > 0
                    ):
                        source_data["credentials"] = docker_credentials

                    DockerDeploymentChange.objects.create(
                        field=DockerDeploymentChange.ChangeField.SOURCE,
                        new_value=source_data,
                        type=DockerDeploymentChange.ChangeType.UPDATE,
                        service=service,
                    )

                    service.save()
                except IntegrityError:
                    raise ResourceConflict(
                        detail=f"A service with the slug `{service_slug}` already exists."
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
                DockerSourceFieldChangeSerializer,
                DockerCommandFieldChangeSerializer,
                HealthcheckFieldChangeSerializer,
                ResourceLimitChangeSerializer,
            ],
            resource_type_field_name="field",
        ),
        responses={
            200: DockerServiceSerializer,
        },
        operation_id="requestDeploymentChanges",
        summary="Request config changes",
        description="Request a change to the configuration of a service.",
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
            "command": DockerCommandFieldChangeSerializer,
            "source": DockerSourceFieldChangeSerializer,
            "healthcheck": HealthcheckFieldChangeSerializer,
            "resource_limits": ResourceLimitChangeSerializer,
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
                    case "command":
                        old_value = getattr(service, field)
                    case "resource_limits":
                        if new_value is not None and len(new_value) == 0:
                            new_value = None
                        old_value = getattr(service, field)
                    case "source":
                        if new_value.get("credentials") is not None and (
                            len(new_value["credentials"]) == 0
                            or new_value.get("credentials")
                            == {
                                "username": "",
                                "password": "",
                            }
                        ):
                            new_value["credentials"] = None
                        old_value = {
                            "image": service.image,
                            "credentials": service.credentials,
                        }
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

                if new_value != old_value:
                    service.add_change(
                        DockerDeploymentChange(
                            type=change_type,
                            field=field,
                            old_value=old_value,
                            new_value=new_value,
                            service=service,
                            item_id=item_id,
                        )
                    )

                response = DockerServiceSerializer(service)
                return Response(response.data, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
class BulkRequestDockerServiceDeploymentChangesAPIView(APIView):
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

        for change in request.data:
            field_serializer_map = {
                "urls": URLItemChangeSerializer,
                "volumes": VolumeItemChangeSerializer,
                "env_variables": EnvItemChangeSerializer,
                "ports": PortItemChangeSerializer,
                "command": DockerCommandFieldChangeSerializer,
                "source": DockerSourceFieldChangeSerializer,
                "healthcheck": HealthcheckFieldChangeSerializer,
                "resource_limits": ResourceLimitChangeSerializer,
            }

            request_serializer = DockerDeploymentFieldChangeRequestSerializer(
                data=change
            )
            if request_serializer.is_valid(raise_exception=True):
                form_serializer_class: type[Serializer] = field_serializer_map[
                    request_serializer.data["field"]
                ]
                form = form_serializer_class(data=change, context={"service": service})
                if form.is_valid(raise_exception=True):
                    data = form.data
                    field = data["field"]
                    new_value = data.get("new_value")
                    item_id = data.get("item_id")
                    change_type = data.get("type")
                    old_value: Any = None
                    match field:
                        case "image" | "command":
                            old_value = getattr(service, field)
                        case "resource_limits":
                            if new_value is not None and len(new_value) == 0:
                                new_value = None
                            old_value = getattr(service, field)
                        case "credentials":
                            if new_value is not None and (
                                len(new_value) == 0
                                or new_value
                                == {
                                    "username": "",
                                    "password": "",
                                }
                            ):
                                new_value = None
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
                    if new_value != old_value:
                        service.add_change(
                            DockerDeploymentChange(
                                type=change_type,
                                field=field,
                                old_value=old_value,
                                new_value=new_value,
                                service=service,
                                item_id=item_id,
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
        summary="Cancel a config change",
        description="Cancel a config change that was requested.",
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
                    detail="Cannot revert this change because it would remove the image of the service."
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
                        f"Cannot revert this change because there is a healthcheck of type `path` attached to the service"
                        f" and the service is not exposed to the public through an URL or another HTTP port"
                    )

            found_change.delete()
            return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class ApplyDockerServiceDeploymentChangesAPIView(APIView):
    serializer_class = DockerServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=DockerServiceDeployRequestSerializer,
        operation_id="applyDeploymentChanges",
        summary="Deploy a docker service",
        description="Apply all pending changes for the service and trigger a new deployment.",
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

        form = DockerServiceDeployRequestSerializer(
            data=request.data if request.data is not None else {}
        )
        if form.is_valid(raise_exception=True):
            commit_message = form.data.get("commit_message")
            new_deployment = DockerDeployment.objects.create(
                service=service,
                commit_message=commit_message if commit_message else "update service",
            )
            service.apply_pending_changes(deployment=new_deployment)

            if service.http_port is not None:
                new_deployment.url = f"{project.slug}-{service_slug}-docker-{new_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}".lower()

            latest_deployment = service.latest_production_deployment
            new_deployment.slot = DockerDeployment.get_next_deployment_slot(
                latest_deployment
            )
            new_deployment.service_snapshot = DockerServiceSerializer(service).data
            new_deployment.save()

            payload = DockerDeploymentDetails.from_deployment(deployment=new_deployment)

            transaction.on_commit(
                lambda: start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                )
            )

            response = DockerServiceDeploymentSerializer(new_deployment)
            return Response(response.data, status=status.HTTP_200_OK)


class RedeployDockerServiceAPIView(APIView):
    serializer_class = DockerServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=None,
        operation_id="redeployDockerService",
        summary="Redeploy a docker service",
        description="Revert the service to the state of a previous deployment.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
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
            deployment = service.deployments.get(hash=deployment_hash)
        except DockerDeployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

        latest_deployment = service.latest_production_deployment

        changes = compute_docker_changes_from_snapshots(
            latest_deployment.service_snapshot, deployment.service_snapshot
        )

        for change in changes:
            service.add_change(change)

        new_deployment = DockerDeployment.objects.create(
            service=service, is_redeploy_of=deployment
        )
        service.apply_pending_changes(deployment=new_deployment)

        new_deployment.slot = DockerDeployment.get_next_deployment_slot(
            latest_deployment
        )
        if len(service.urls.all()) > 0:
            new_deployment.url = f"{project.slug}-{service_slug}-docker-{new_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}".lower()

        new_deployment.service_snapshot = DockerServiceSerializer(service).data
        new_deployment.save()

        payload = DockerDeploymentDetails.from_deployment(new_deployment)

        transaction.on_commit(
            lambda: start_workflow(
                DeployDockerServiceWorkflow.run,
                payload,
                id=payload.workflow_id,
            )
        )

        response = DockerServiceDeploymentSerializer(new_deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class CancelDockerServiceDeploymentAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        request=None,
        responses={409: ErrorResponse409Serializer, 200: DockerServiceSerializer},
        operation_id="cancelDockerServiceDeployment",
        summary="Cancel deployment",
        description="Cancel a deployment in progress.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
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
            deployment = service.deployments.get(hash=deployment_hash)
        except DockerDeployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

        if deployment.finished_at is not None or deployment.status not in [
            DockerDeployment.DeploymentStatus.QUEUED,
            DockerDeployment.DeploymentStatus.PREPARING,
            DockerDeployment.DeploymentStatus.STARTING,
            DockerDeployment.DeploymentStatus.RESTARTING,
        ]:
            raise ResourceConflict(
                detail="This deployment cannot be cancelled as it has already finished "
                "or is in the process of cancelling."
            )

        if deployment.started_at is None:
            deployment.status = DockerDeployment.DeploymentStatus.CANCELLED
            deployment.status_reason = "Deployment cancelled."
            deployment.save()

        transaction.on_commit(
            lambda: workflow_signal(
                workflow=DeployDockerServiceWorkflow.run,
                arg=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                signal=DeployDockerServiceWorkflow.cancel_deployment,
                workflow_id=deployment.workflow_id,
            )
        )

        response = DockerServiceDeploymentSerializer(deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class DockerServiceDetailsAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceUpdateRequestSerializer,
        operation_id="updateService",
        summary="Update a service",
    )
    def patch(self, request: Request, project_slug: str, service_slug: str) -> Response:
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

        form = DockerServiceUpdateRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            try:
                service.slug = form.data.get("slug", project.slug)
                service.save()
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"The slug `{service_slug}` is already used by another service."
                )
            else:
                response = DockerServiceSerializer(service)
                return Response(response.data)

    @extend_schema(
        operation_id="getDockerService",
        summary="Get single service",
        description="See all the details of a service.",
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
    pagination_class = DeploymentListPagination
    queryset = (
        DockerDeployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    @extend_schema(
        summary="List all deployments",
        description="List all deployments for a service, the default order is last created descendant.",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e

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
            .order_by("-queued_at")
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

    @extend_schema(summary="Get single deployment")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DockerServiceDeploymentLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer

    @extend_schema(
        summary="Get deployment logs", parameters=[DeploymentLogsQuerySerializer]
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
    ):
        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            deployment = DockerDeployment.objects.get(
                service=service, hash=deployment_hash
            )
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
        else:
            form = DeploymentLogsQuerySerializer(data=request.query_params)
            if form.is_valid(raise_exception=True):
                search_client = SearchClient(host=settings.ELASTICSEARCH_HOST)
                data = search_client.search(
                    index_name=settings.ELASTICSEARCH_LOGS_INDEX,
                    query=dict(**form.validated_data, deployment_id=deployment.hash),
                )
                return Response(data)


class DockerServiceDeploymentHttpLogsAPIView(ListAPIView):
    serializer_class = HttpLogSerializer
    queryset = (
        HttpLog.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = DeploymentLogsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeploymentHttpLogsFilterSet

    @extend_schema(
        summary="Get deployment HTTP logs",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid cursor" in str(e.detail):
                return Response(EMPTY_CURSOR_RESPONSE)
            raise e

    def get_queryset(self):
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        deployment_hash = self.kwargs["deployment_hash"]

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            deployment = DockerDeployment.objects.get(
                service=service, hash=deployment_hash
            )
            return deployment.http_logs
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
        summary="Archive a docker service",
        description="Archive a service created from a docker image.",
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

        if service.deployments.count() > 0:
            archived_project: ArchivedProject = (
                project.archived_version
                if hasattr(project, "archived_version")
                else None
            )
            if archived_project is None:
                archived_project = ArchivedProject.create_from_project(project)

            archived_service = ArchivedDockerService.create_from_service(
                service, archived_project
            )

            payload = ArchivedServiceDetails(
                original_id=archived_service.original_id,
                urls=[
                    URLDto(
                        domain=url.domain,
                        base_path=url.base_path,
                        strip_prefix=url.strip_prefix,
                        id=url.original_id,
                    )
                    for url in archived_service.urls.all()
                ],
                volumes=[
                    VolumeDto(
                        container_path=volume.container_path,
                        mode=volume.mode,
                        name=volume.name,
                        host_path=volume.host_path,
                        id=volume.original_id,
                    )
                    for volume in archived_service.volumes.all()
                ],
                project_id=archived_project.original_id,
                deployments=[
                    SimpleDeploymentDetails(
                        hash=dpl.get("hash"),
                        url=dpl.get("url"),
                        project_id=archived_service.project.original_id,
                        service_id=archived_service.original_id,
                    )
                    for dpl in archived_service.deployments
                ],
            )

            transaction.on_commit(
                lambda: start_workflow(
                    workflow=ArchiveDockerServiceWorkflow.run,
                    arg=payload,
                    id=archived_service.workflow_id,
                )
            )

        service.delete_resources()
        service.delete()

        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class ToggleDockerServiceAPIView(APIView):
    serializer_class = DockerServiceDeploymentSerializer

    @extend_schema(
        operation_id="toggleDockerService",
        request=None,
        responses={
            409: ErrorResponse409Serializer,
            200: DockerServiceDeploymentSerializer,
        },
        summary="Stop/Restart a docker service",
        description="Stops a running docker service and restart it if it was stopped.",
    )
    @transaction.atomic()
    def put(self, request: Request, project_slug: str, service_slug: str):
        project: Project | None = (
            Project.objects.filter(
                slug=project_slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )

        service: DockerRegistryService | None = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            ).select_related("project")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        production_deployment = service.latest_production_deployment
        if production_deployment is None:
            raise ResourceConflict(
                "This service has not been deployed yet, and thus its state cannot be toggled."
            )

        payload = SimpleDeploymentDetails(
            hash=production_deployment.hash,
            project_id=project.id,
            service_id=service.id,
            status=production_deployment.status,
            service_snapshot=production_deployment.service_snapshot,
        )
        transaction.on_commit(
            lambda: start_workflow(
                workflow=ToggleDockerServiceWorkflow.run,
                arg=payload,
                id=f"toggle-{service.id}-{project.id}",
            )
        )

        response = DockerServiceDeploymentSerializer(production_deployment)
        return Response(response.data, status=status.HTTP_200_OK)
