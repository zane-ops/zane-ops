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
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView


from search.loki_client import LokiSearchClient
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
    ConfigItemChangeSerializer,
    DeploymentLogsQuerySerializer,
    DockerServiceCreateRequestSerializer,
    DockerServiceDeploymentFilterSet,
    DockerServiceUpdateRequestSerializer,
    DockerSourceFieldChangeSerializer,
    EnvStringChangeSerializer,
    HttpLogFieldsQuerySerializer,
    HttpLogFieldsResponseSerializer,
    VolumeItemChangeSerializer,
    DockerCommandFieldChangeSerializer,
    URLItemChangeSerializer,
    EnvItemChangeSerializer,
    PortItemChangeSerializer,
    HealthcheckFieldChangeSerializer,
    DockerDeploymentFieldChangeRequestSerializer,
    DeploymentListPagination,
    DeploymentHttpLogsPagination,
    DeploymentHttpLogsFilterSet,
    DockerServiceDeployRequestSerializer,
    ResourceLimitChangeSerializer,
)
from ..dtos import ConfigDto, URLDto, VolumeDto
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    ArchivedProject,
    ArchivedDockerService,
    DockerDeploymentChange,
    HttpLog,
    DeploymentURL,
    Environment,
)
from ..serializers import (
    ConfigSerializer,
    DockerServiceDeploymentSerializer,
    DockerServiceSerializer,
    HealthCheckSerializer,
    VolumeSerializer,
    URLModelSerializer,
    PortConfigurationSerializer,
    DockerEnvVariableSerializer,
    ErrorResponse409Serializer,
    HttpLogSerializer,
    EnvironmentSerializer,
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
from ..utils import Colors, generate_random_chars
from io import StringIO

from dotenv import dotenv_values


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
    def post(self, request: Request, project_slug: str, env_slug: str | None = None):
        try:
            project = Project.objects.get(slug=project_slug, owner=request.user)
            # if env_slug is None:
            environment = project.production_env
            # else:
            #   environment = Environment.objects.get()
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                f"A project with the slug `{project_slug}` does not exist"
            )
        else:
            form = DockerServiceCreateRequestSerializer(data=request.data)
            if form.is_valid(raise_exception=True):
                data = form.data

                # Create service in DB
                docker_credentials: dict | None = data.get("credentials")  # type: ignore
                fake = Faker()
                Faker.seed(time.monotonic())
                service_slug = data.get("slug", fake.slug()).lower()  # type: ignore
                try:
                    service = DockerRegistryService.objects.create(
                        slug=service_slug,
                        project=project,
                        deploy_token=generate_random_chars(20),
                        environment=environment,
                    )

                    service.network_alias = f"zn-{service.slug}-{service.unprefixed_id}"

                    source_data = {
                        "image": data["image"],  # type: ignore
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
                ConfigItemChangeSerializer,
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
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
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
            .select_related("project", "healthcheck")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        field_serializer_map = {
            DockerDeploymentChange.ChangeField.URLS: URLItemChangeSerializer,
            DockerDeploymentChange.ChangeField.VOLUMES: VolumeItemChangeSerializer,
            DockerDeploymentChange.ChangeField.ENV_VARIABLES: EnvItemChangeSerializer,
            DockerDeploymentChange.ChangeField.PORTS: PortItemChangeSerializer,
            DockerDeploymentChange.ChangeField.COMMAND: DockerCommandFieldChangeSerializer,
            DockerDeploymentChange.ChangeField.SOURCE: DockerSourceFieldChangeSerializer,
            DockerDeploymentChange.ChangeField.HEALTHCHECK: HealthcheckFieldChangeSerializer,
            DockerDeploymentChange.ChangeField.RESOURCE_LIMITS: ResourceLimitChangeSerializer,
            DockerDeploymentChange.ChangeField.CONFIGS: ConfigItemChangeSerializer,
        }

        request_serializer = DockerDeploymentFieldChangeRequestSerializer(
            data=request.data
        )
        if request_serializer.is_valid(raise_exception=True):
            form_serializer_class: type[Serializer] = field_serializer_map[
                request_serializer.data["field"]  # type: ignore
            ]
            form = form_serializer_class(
                data=request.data, context={"service": service}
            )
            if form.is_valid(raise_exception=True):
                data = form.data
                field = data["field"]  # type: ignore
                new_value = data.get("new_value")  # type: ignore
                item_id = data.get("item_id")  # type: ignore
                change_type = data.get("type")  # type: ignore
                old_value: Any = None
                match field:
                    case DockerDeploymentChange.ChangeField.COMMAND:
                        old_value = getattr(service, field)
                    case DockerDeploymentChange.ChangeField.RESOURCE_LIMITS:
                        if new_value is not None and len(new_value) == 0:
                            new_value = None
                        old_value = getattr(service, field)
                    case DockerDeploymentChange.ChangeField.SOURCE:
                        if new_value.get("credentials") is not None and (  # type: ignore
                            len(new_value["credentials"]) == 0  # type: ignore
                            or new_value.get("credentials")  # type: ignore
                            == {
                                "username": "",
                                "password": "",
                            }
                        ):
                            new_value["credentials"] = None  # type: ignore
                        old_value = {
                            "image": service.image,
                            "credentials": service.credentials,
                        }
                    case DockerDeploymentChange.ChangeField.HEALTHCHECK:
                        old_value = (
                            HealthCheckSerializer(service.healthcheck).data
                            if service.healthcheck is not None
                            else None
                        )
                    case DockerDeploymentChange.ChangeField.VOLUMES:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = VolumeSerializer(
                                service.volumes.get(id=item_id)
                            ).data
                    case DockerDeploymentChange.ChangeField.CONFIGS:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = ConfigSerializer(
                                service.configs.get(id=item_id)
                            ).data
                    case DockerDeploymentChange.ChangeField.URLS:
                        old_value = None
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = URLModelSerializer(
                                service.urls.get(id=item_id)
                            ).data
                    case DockerDeploymentChange.ChangeField.PORTS:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = PortConfigurationSerializer(
                                service.ports.get(id=item_id)
                            ).data
                    case DockerDeploymentChange.ChangeField.ENV_VARIABLES:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = DockerEnvVariableSerializer(
                                service.env_variables.get(id=item_id)  # type: ignore
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


class RequestDockerServiceEnvChangesAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        request=EnvStringChangeSerializer,
        operation_id="requestEnvChanges",
        summary="Request env changes",
        description="Request a change to the environments variables of a service.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
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
            .select_related("project", "healthcheck")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        form = EnvStringChangeSerializer(
            data=request.data, context={"service": service}
        )
        if form.is_valid(raise_exception=True):
            data = form.data
            new_value = data.get("new_value")  # type: ignore

            values = dotenv_values(stream=StringIO(new_value))

            for key, value in values.items():
                service.add_change(
                    DockerDeploymentChange(
                        type=DockerDeploymentChange.ChangeType.ADD,
                        field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                        new_value={
                            "key": key,
                            "value": value,
                        },
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
        summary="Cancel a config change",
        description="Cancel a config change that was requested.",
    )
    def delete(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        change_id: str,
        env_slug: str | None = None,
    ):
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
            .select_related("project", "healthcheck")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "changes", "configs"
            )
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

            if snapshot.has_duplicate_volumes():
                raise ResourceConflict(
                    detail="Cannot revert this change as it would cause duplicate volumes with the same host path or container path for this service."
                )

            if snapshot.has_duplicate_configs():
                raise ResourceConflict(
                    detail="Cannot revert this change as it would cause duplicate config files with the same mounth path for this service."
                )

            found_change.delete()
            return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class DeployDockerServiceAPIView(APIView):
    serializer_class = DockerServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=DockerServiceDeployRequestSerializer,
        operation_id="deployDockerService",
        summary="Deploy a docker service",
        description="Apply all pending changes for the service and trigger a new deployment.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
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
            .select_related("project", "healthcheck")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "changes", "configs"
            )
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
            commit_message = form.data.get("commit_message")  # type: ignore
            new_deployment = DockerDeployment.objects.create(
                service=service,
                commit_message=commit_message if commit_message else "update service",
            )
            service.apply_pending_changes(deployment=new_deployment)

            if service.urls.filter(associated_port__isnull=False).count() > 0:
                ports = (
                    service.urls.filter(associated_port__isnull=False)
                    .values_list("associated_port", flat=True)
                    .distinct()
                )
                for port in ports:
                    DeploymentURL.generate_for_deployment(
                        deployment=new_deployment,
                        service=service,
                        port=port,
                    )

            latest_deployment = service.latest_production_deployment
            new_deployment.slot = DockerDeployment.get_next_deployment_slot(
                latest_deployment
            )
            new_deployment.service_snapshot = DockerServiceSerializer(service).data  # type: ignore
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
        env_slug: str | None = None,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
            environment = project.production_env
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project", "healthcheck")
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

        latest_deployment: DockerDeployment = service.latest_production_deployment  # type: ignore

        changes = compute_docker_changes_from_snapshots(
            dict(**latest_deployment.service_snapshot, environment=EnvironmentSerializer(environment).data),  # type: ignore
            dict(**deployment.service_snapshot, environment=EnvironmentSerializer(environment).data),  # type: ignore
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
        if service.urls.filter(associated_port__isnull=False).count() > 0:
            ports = (
                service.urls.filter(associated_port__isnull=False)
                .values_list("associated_port", flat=True)
                .distinct()
            )
            for port in ports:
                DeploymentURL.generate_for_deployment(
                    deployment=new_deployment,
                    service=service,
                    port=port,
                )

        new_deployment.service_snapshot = DockerServiceSerializer(service).data  # type: ignore
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
        env_slug: str | None = None,
    ):
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
            .select_related("project", "healthcheck")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        try:
            deployment = service.deployments.get(hash=deployment_hash)  # type: ignore
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
                signal=DeployDockerServiceWorkflow.cancel_deployment,  # type: ignore
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
    def patch(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ) -> Response:
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
            .select_related("project", "healthcheck")
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
                service.slug = form.data.get("slug", project.slug)  # type: ignore
                service.save()
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"The slug `{service_slug}` is already used by another service."
                )
            else:
                response = DockerServiceSerializer(service)
                return Response(response.data)
        raise NotImplementedError("unreachable")

    @extend_schema(
        operation_id="getDockerService",
        summary="Get single service",
        description="See all the details of a service.",
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
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
            .select_related("project", "healthcheck")
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

    def get_queryset(self) -> QuerySet[DockerDeployment]:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        env_slug = self.kwargs.get("env_slug")

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

    def get_object(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        env_slug = self.kwargs.get("env_slug")
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
        env_slug: str | None = None,
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
            print(f"{request.query_params=}")
            if form.is_valid(raise_exception=True):
                search_client = LokiSearchClient(host=settings.LOKI_HOST)
                data = search_client.search(
                    query=dict(**form.validated_data, deployment_id=deployment.hash),  # type: ignore
                )
                return Response(data)


class DockerServiceDeploymentHttpLogsFieldsAPIView(APIView):
    serializer_class = HttpLogFieldsResponseSerializer

    @extend_schema(
        summary="Get deployment http logs fields values",
        parameters=[HttpLogFieldsQuerySerializer],
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
        env_slug: str | None = None,
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
            form = HttpLogFieldsQuerySerializer(data=request.query_params)
            if form.is_valid(raise_exception=True):
                field = form.data["field"]  # type: ignore # type: ignore
                value = form.data["value"]  # type: ignore # type: ignore

                condition = {}
                if len(value) > 0:
                    condition = {f"{field}__startswith": value}

                values = (
                    HttpLog.objects.filter(
                        deployment_id=deployment.hash,
                        service_id=service.id,
                        **condition,
                    )
                    .order_by(field)
                    .values_list(field, flat=True)
                    .distinct()[:7]
                )

                seriaziler = HttpLogFieldsResponseSerializer([item for item in values])
                return Response(seriaziler.data)


class DockerServiceHttpLogsFieldsAPIView(APIView):
    serializer_class = HttpLogFieldsResponseSerializer

    @extend_schema(
        summary="Get service http logs fields values",
        parameters=[HttpLogFieldsQuerySerializer],
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
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
        else:
            form = HttpLogFieldsQuerySerializer(data=request.query_params)
            if form.is_valid(raise_exception=True):
                field = form.data["field"]  # type: ignore
                value = form.data["value"]  # type: ignore

                condition = {}
                if len(value) > 0:
                    condition = {f"{field}__startswith": value}

                values = (
                    HttpLog.objects.filter(
                        service_id=service.id,
                        **condition,
                    )
                    .order_by(field)
                    .values_list(field, flat=True)
                    .distinct()[:7]
                )

                seriaziler = HttpLogFieldsResponseSerializer([item for item in values])
                return Response(seriaziler.data)


class DockerServiceDeploymentHttpLogsAPIView(ListAPIView):
    serializer_class = HttpLogSerializer
    queryset = (
        HttpLog.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = DeploymentHttpLogsPagination
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

    def get_queryset(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        deployment_hash = self.kwargs["deployment_hash"]
        env_slug = self.kwargs["env_slug"]

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


class DockerServiceHttpLogsAPIView(ListAPIView):
    serializer_class = HttpLogSerializer
    queryset = (
        HttpLog.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = DeploymentHttpLogsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeploymentHttpLogsFilterSet

    @extend_schema(
        summary="Get service HTTP logs",
    )
    def get(self, request: Request, *args, **kwargs):
        try:
            print("====== HTTP LOGS SEARCH ======")
            print(f"Params: {Colors.GREY}{request.query_params}{Colors.ENDC}")
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid cursor" in str(e.detail):
                return Response(EMPTY_CURSOR_RESPONSE)
            raise e

    def get_queryset(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        env_slug = self.kwargs.get("service_slug")

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            return service.http_logs
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except DockerRegistryService.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )


class DockerServiceDeploymentSingleHttpLogAPIView(RetrieveAPIView):
    serializer_class = HttpLogSerializer
    queryset = (
        HttpLog.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    lookup_url_kwarg = "request_uuid"  # This corresponds to the URL configuration

    @extend_schema(summary="Get single deployment http log")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        deployment_hash = self.kwargs["deployment_hash"]
        request_uuid = self.kwargs["request_uuid"]
        env_slug = self.kwargs.get("env_slug")

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            deployment = DockerDeployment.objects.get(
                service=service, hash=deployment_hash
            )
            http_log = deployment.http_logs.filter(
                deployment_id=deployment_hash, request_id=request_uuid
            ).first()

            if http_log is None:
                raise exceptions.NotFound(
                    detail=f"A HTTP log with the id of `{request_uuid}` does not exist for this deployment."
                )
            return http_log
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


class DockerServiceSingleHttpLogAPIView(RetrieveAPIView):
    serializer_class = HttpLogSerializer
    queryset = (
        HttpLog.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    lookup_url_kwarg = "request_uuid"  # This corresponds to the URL configuration

    @extend_schema(summary="Get single service http log")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        request_uuid = self.kwargs["request_uuid"]
        env_slug = self.kwargs.get("env_slug")

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            http_log = service.http_logs.filter(
                service_id=service.id, request_id=request_uuid
            ).first()

            if http_log is None:
                raise exceptions.NotFound(
                    detail=f"A HTTP log with the id of `{request_uuid}` does not exist for this deployment."
                )
            return http_log
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except DockerRegistryService.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
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
    def delete(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
        project = (
            Project.objects.filter(
                slug=project_slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )

        service = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project", "healthcheck")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        if service.deployments.count() > 0:  # type: ignore
            archived_project: ArchivedProject | None = (
                project.archived_version  # type: ignore
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
                configs=[
                    ConfigDto(
                        mount_path=config.mount_path,
                        name=config.name,
                        id=config.original_id,
                        language=config.language,
                        contents=config.contents,
                    )
                    for config in archived_service.configs.all()
                ],
                project_id=archived_project.original_id,
                deployments=[
                    SimpleDeploymentDetails(
                        hash=dpl.get("hash"),  # type: ignore
                        urls=dpl.get("urls"),  # type: ignore
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
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str | None = None,
    ):
        project: Project | None = (
            Project.objects.filter(
                slug=project_slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )

        service = (
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
