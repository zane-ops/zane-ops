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

from . import EMPTY_PAGINATED_RESPONSE, EMPTY_CURSOR_RESPONSE
from .base import EMPTY_RESPONSE, ResourceConflict
from .helpers import (
    compute_docker_service_snapshot_without_changes,
    compute_docker_changes_from_snapshots,
)
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
    DeploymentListPagination,
    DeploymentLogsPagination,
    DeploymentLogsFilterSet,
    DeploymentHttpLogsFilterSet,
    DockerServiceDeployServiceSerializer,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
    SimpleLog,
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
    SimpleLogSerializer,
    HttpLogSerializer,
)
from ..tasks import (
    delete_resources_for_docker_service,
    deploy_docker_service_with_changes,
)


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
                    )

                    service.network_alias = f"{service.slug}-{service.unprefixed_id}"

                    initial_changes = [
                        DockerDeploymentChange(
                            field=DockerDeploymentChange.ChangeField.IMAGE,
                            new_value=data["image"],
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            service=service,
                        )
                    ]

                    if docker_credentials is not None:
                        initial_changes.append(
                            DockerDeploymentChange(
                                field=DockerDeploymentChange.ChangeField.CREDENTIALS,
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
                "credentials": DockerCredentialsFieldChangeSerializer,
                "command": DockerCommandFieldChangeSerializer,
                "image": DockerImageFieldChangeSerializer,
                "healthcheck": HealthcheckFieldChangeSerializer,
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
        request=DockerServiceDeployServiceSerializer,
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

        form = DockerServiceDeployServiceSerializer(
            data=request.data if request.data is not None else {}
        )
        if form.is_valid(raise_exception=True):
            commit_message = form.data.get("commit_message")
            new_deployment = DockerDeployment.objects.create(
                service=service,
                commit_message=commit_message if commit_message else "update service",
            )
            service.apply_pending_changes(deployment=new_deployment)

            if len(service.urls.all()) > 0:
                new_deployment.url = f"{project.slug}-{service_slug}-docker-{new_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}".lower()

            latest_deployment = service.latest_production_deployment
            if (
                latest_deployment is not None
                and latest_deployment.slot == DockerDeployment.DeploymentSlot.BLUE
                and latest_deployment.status != DockerDeployment.DeploymentStatus.FAILED
                # 👆🏽 technically this can only be true for the initial deployment
                # for the next deployments, when they fail, they will not be promoted to production
            ):
                new_deployment.slot = DockerDeployment.DeploymentSlot.GREEN
            else:
                new_deployment.slot = DockerDeployment.DeploymentSlot.BLUE

            new_deployment.service_snapshot = DockerServiceSerializer(service).data
            new_deployment.save()

            token = Token.objects.get(user=request.user)
            # Run celery deployment task
            transaction.on_commit(
                lambda: deploy_docker_service_with_changes.apply_async(
                    kwargs=dict(
                        deployment_hash=new_deployment.hash,
                        service_id=service.id,
                        auth_token=token.key,
                    ),
                    task_id=new_deployment.task_id,
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

        if (
            latest_deployment is not None
            and latest_deployment.slot == DockerDeployment.DeploymentSlot.BLUE
            and latest_deployment.status != DockerDeployment.DeploymentStatus.FAILED
            # 👆🏽 technically this can only be true for the initial deployment
            # for the next deployments, when they fail, they will not be promoted to production
        ):
            new_deployment.slot = DockerDeployment.DeploymentSlot.GREEN
        else:
            new_deployment.slot = DockerDeployment.DeploymentSlot.BLUE

        if len(service.urls.all()) > 0:
            new_deployment.url = f"{project.slug}-{service_slug}-docker-{new_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}".lower()

        new_deployment.service_snapshot = DockerServiceSerializer(service).data
        new_deployment.save()

        token = Token.objects.get(user=request.user)
        # Run celery deployment task
        transaction.on_commit(
            lambda: deploy_docker_service_with_changes.apply_async(
                kwargs=dict(
                    deployment_hash=new_deployment.hash,
                    service_id=service.id,
                    auth_token=token.key,
                ),
                task_id=new_deployment.task_id,
            )
        )

        response = DockerServiceDeploymentSerializer(new_deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class GetDockerServiceAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
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


class DockerServiceDeploymentLogsAPIView(ListAPIView):
    serializer_class = SimpleLogSerializer
    queryset = (
        SimpleLog.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = DeploymentLogsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeploymentLogsFilterSet

    @extend_schema(
        summary="Get deployment logs",
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
            return deployment.logs
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

            archive_task_id = service.archive_task_id

            transaction.on_commit(
                lambda: delete_resources_for_docker_service.apply_async(
                    kwargs=dict(archived_service_id=archived_service.id),
                    task_id=archive_task_id,
                )
            )

        service.delete_resources()
        service.delete()

        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)
