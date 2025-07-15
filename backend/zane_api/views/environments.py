from typing import Any, Callable, List, Tuple
from django.db import IntegrityError, transaction
from django.db.models import Q
from drf_spectacular.utils import (
    extend_schema,
)
from rest_framework import exceptions
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import ResourceConflict
from .serializers import (
    CreateEnvironmentRequestSerializer,
    CloneEnvironmentRequestSerializer,
)
from ..models import (
    Project,
    ArchivedProject,
    Service,
    ArchivedDockerService,
    PortConfiguration,
    URL,
    Volume,
    Config,
    Environment,
    DeploymentChange,
    Deployment,
    DeploymentURL,
    SharedEnvVariable,
    ArchivedGitService,
)
from ..serializers import (
    EnvironmentSerializer,
    EnvironmentWithServicesSerializer,
    ServiceSerializer,
    SharedEnvVariableSerializer,
    ErrorResponse409Serializer,
)
from temporal.client import TemporalClient
from temporal.workflows import (
    DeployGitServiceWorkflow,
    CreateEnvNetworkWorkflow,
    ArchiveEnvWorkflow,
    DeployDockerServiceWorkflow,
)
from temporal.shared import (
    EnvironmentDetails,
    DeploymentDetails,
)
from ..git_client import GitClient
from .helpers import compute_docker_changes_from_snapshots
from rest_framework import viewsets


class CreateEnviromentAPIView(APIView):
    serializer_class = EnvironmentSerializer

    @extend_schema(
        request=CreateEnvironmentRequestSerializer,
        responses={
            201: EnvironmentSerializer,
            409: ErrorResponse409Serializer,
        },
        operation_id="createNewEnvironment",
        summary="Create new environment",
        description="Create empty environment with no services in it",
    )
    @transaction.atomic()
    def post(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )

        form = CreateEnvironmentRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        name = form.data["name"].lower()  # type: ignore
        try:
            environment = project.environments.create(name=name)
        except IntegrityError:
            raise ResourceConflict(
                f"An environment with the name `{name}` already exists"
            )
        else:
            workflow_id = environment.workflow_id
            serializer = EnvironmentSerializer(environment)
            transaction.on_commit(
                lambda: TemporalClient.start_workflow(
                    CreateEnvNetworkWorkflow.run,
                    EnvironmentDetails(
                        id=environment.id, project_id=project.id, name=environment.name
                    ),
                    id=workflow_id,
                )
            )
            return Response(status=status.HTTP_201_CREATED, data=serializer.data)


class CloneEnviromentAPIView(APIView):
    serializer_class = EnvironmentWithServicesSerializer

    @extend_schema(
        request=CloneEnvironmentRequestSerializer,
        responses={
            201: EnvironmentWithServicesSerializer,
            409: ErrorResponse409Serializer,
        },
        operation_id="cloneEnvironment",
        summary="Clone environment",
        description="Create new environment from another",
    )
    @transaction.atomic()
    def post(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            current_environment = project.environments.get(name=env_slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )

        form = CloneEnvironmentRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        name = form.data["name"].lower()  # type: ignore
        should_deploy_services = form.data["deploy_services"]  # type: ignore

        try:
            new_environment = project.environments.create(name=name)
        except IntegrityError:
            raise ResourceConflict(
                f"An environment with the name `{name}` already exists in this project"
            )
        else:
            # copy variables
            cloned_variables: List[SharedEnvVariable] = [
                SharedEnvVariable(
                    key=variable.key, value=variable.value, environment=new_environment
                )
                for variable in current_environment.variables.all()  # type: ignore
            ]

            if len(cloned_variables) > 0:
                new_environment.variables.bulk_create(cloned_variables)  # type: ignore

            workflows_to_run: List[Tuple[Callable, Any, str]] = [
                (
                    CreateEnvNetworkWorkflow.run,
                    EnvironmentDetails(
                        id=new_environment.id,
                        project_id=project.id,
                        name=new_environment.name,
                    ),
                    new_environment.workflow_id,
                )
            ]

            all_services = (
                current_environment.services.select_related(
                    "healthcheck", "project", "environment"
                )
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes", "configs"
                )
                .all()
            )

            for service in all_services:
                cloned_service = service.clone(environment=new_environment)
                current = ServiceSerializer(cloned_service).data
                target = ServiceSerializer(service).data
                changes = compute_docker_changes_from_snapshots(current, target)  # type: ignore

                for change in changes:
                    match change.field:
                        case DeploymentChange.ChangeField.URLS:
                            if change.new_value.get("redirect_to") is not None:  # type: ignore
                                # we don't copy over redirected urls, as they might not be needed
                                continue
                            # We also don't want to copy the same URL because it might clash with the original service
                            change.new_value["domain"] = URL.generate_default_domain(cloned_service)  # type: ignore
                        case DeploymentChange.ChangeField.PORTS:
                            # Don't copy port changes to not cause conflicts with other ports
                            continue
                    change.service = cloned_service
                    change.save()

                if should_deploy_services and service.deployments.count() > 0:
                    if cloned_service.type == Service.ServiceType.DOCKER_REGISTRY:
                        new_deployment = cloned_service.prepare_new_docker_deployment()
                    else:
                        new_deployment = cloned_service.prepare_new_git_deployment()
                    payload = DeploymentDetails.from_deployment(
                        deployment=new_deployment
                    )
                    workflows_to_run.append(
                        (
                            (
                                DeployDockerServiceWorkflow.run
                                if service.type == Service.ServiceType.DOCKER_REGISTRY
                                else DeployGitServiceWorkflow.run
                            ),
                            payload,
                            payload.workflow_id,
                        )
                    )

            transaction.on_commit(
                lambda: [
                    TemporalClient.start_workflow(
                        workflow,
                        payload,
                        workflow_id,
                    )
                    for workflow, payload, workflow_id in workflows_to_run
                ]
            )

            serializer = EnvironmentWithServicesSerializer(new_environment)
            return Response(status=status.HTTP_201_CREATED, data=serializer.data)


class EnvironmentDetailsAPIView(APIView):
    serializer_class = EnvironmentSerializer

    @extend_schema(
        responses={200: EnvironmentWithServicesSerializer},
        operation_id="getEnvironment",
        summary="Get a single environment",
    )
    def get(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )
        serializer = EnvironmentWithServicesSerializer(environment)
        return Response(data=serializer.data)

    @extend_schema(
        request=CreateEnvironmentRequestSerializer,
        operation_id="updateEnvironment",
        summary="Update an environment",
    )
    def patch(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )
        if environment.name == Environment.PRODUCTION_ENV:
            raise exceptions.PermissionDenied(
                "Cannot rename the production environment."
            )

        form = CreateEnvironmentRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        name = form.data["name"].lower()  # type: ignore

        try:
            environment.name = name
            environment.save()
        except IntegrityError:
            raise ResourceConflict(
                f"An environment with the name `{name}` already exists in this project"
            )
        serializer = EnvironmentSerializer(environment)
        return Response(data=serializer.data)

    @extend_schema(
        responses={204: None},
        operation_id="archiveEnvironment",
        summary="Archive environment",
        description="Archive environment with the services inside of it",
    )
    @transaction.atomic()
    def delete(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )

        if environment.name == Environment.PRODUCTION_ENV:
            raise exceptions.PermissionDenied(
                "Cannot delete the production environment"
            )

        archived_version = ArchivedProject.get_or_create_from_project(project)

        docker_service_list = (
            Service.objects.filter(Q(project=project) & Q(environment=environment))
            .select_related("project", "healthcheck", "environment")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        )
        id_list = []
        for service in docker_service_list:
            if service.deployments.count() > 0:
                if service.type == Service.ServiceType.DOCKER_REGISTRY:
                    ArchivedDockerService.create_from_service(service, archived_version)
                else:
                    ArchivedGitService.create_from_service(service, archived_version)
                id_list.append(service.id)

        PortConfiguration.objects.filter(Q(service__id__in=id_list)).delete()
        URL.objects.filter(Q(service__id__in=id_list)).delete()
        Volume.objects.filter(Q(service__id__in=id_list)).delete()
        Config.objects.filter(Q(service__id__in=id_list)).delete()
        Config.objects.filter(Q(service__id__in=id_list)).delete()
        for service in docker_service_list:
            if service.healthcheck is not None:
                service.healthcheck.delete()
        docker_service_list.delete()

        details = EnvironmentDetails(
            id=environment.id, project_id=project.id, name=environment.name
        )
        workflow_id = environment.archive_workflow_id
        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                ArchiveEnvWorkflow.run,
                details,
                id=workflow_id,
            )
        )

        environment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SharedEnvVariablesViewSet(viewsets.ModelViewSet):
    serializer_class = SharedEnvVariableSerializer
    pagination_class = None
    queryset = (
        SharedEnvVariable.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    def get_queryset(self):
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]
        pk = self.kwargs.get("pk")

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            if pk is not None:
                environment.variables.get(id=pk)  # type: ignore
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except SharedEnvVariable.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A variable with the id `{pk}` does not exist in this environment"
            )

        return environment.variables.all()  # type: ignore

    def perform_update(self, serializer: SharedEnvVariableSerializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ResourceConflict(
                "Duplicate variable names are not allowed in the same environment"
            )

    def perform_create(self, serializer: SharedEnvVariableSerializer):
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]
        environment = Environment.objects.get(
            name=env_slug.lower(), project__slug=project_slug
        )

        data = serializer.validated_data
        try:
            environment.variables.create(
                key=data["key"],  # type: ignore
                value=data["value"],  # type: ignore
            )  # type: ignore
        except IntegrityError:
            raise ResourceConflict(
                "Duplicate variable names are not allowed in the same environment"
            )
