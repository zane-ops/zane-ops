from typing import Any, Awaitable, Callable, List, Tuple
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
    DockerRegistryService,
    ArchivedDockerService,
    PortConfiguration,
    URL,
    Volume,
    Config,
    Environment,
    DockerDeploymentChange,
    DockerDeployment,
    DeploymentURL,
)
from ..serializers import (
    EnvironmentSerializer,
    EnvironmentWithServicesSerializer,
    DockerServiceSerializer,
)
from ..temporal import (
    start_workflow,
    EnvironmentDetails,
    CreateEnvNetworkWorkflow,
    ArchiveEnvWorkflow,
    DeployDockerServiceWorkflow,
    DockerDeploymentDetails,
)
from .helpers import compute_docker_changes_from_snapshots


class CreateEnviromentAPIView(APIView):
    serializer_class = EnvironmentSerializer

    @extend_schema(
        request=CreateEnvironmentRequestSerializer,
        responses={201: EnvironmentSerializer},
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
                lambda: start_workflow(
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
        responses={201: EnvironmentWithServicesSerializer},
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
                    "volumes", "ports", "urls", "env_variables", "changes"
                )
                .all()
            )

            for service in all_services:
                cloned_service = service.clone(environment=new_environment)
                current = DockerServiceSerializer(cloned_service).data
                target = DockerServiceSerializer(service).data
                changes = compute_docker_changes_from_snapshots(current, target)  # type: ignore

                for change in changes:
                    match change.field:
                        case DockerDeploymentChange.ChangeField.URLS:
                            if change.new_value.get("redirect_to") is not None:  # type: ignore
                                # we don't copy over redirected urls, as they might not be needed
                                continue
                            # We also don't want to copy the same URL because it might clash with the original service
                            change.new_value["domain"] = URL.generate_default_domain(cloned_service)  # type: ignore
                        case DockerDeploymentChange.ChangeField.PORTS:
                            # Don't copy port changes to not cause conflicts with other ports
                            continue
                    change.service = cloned_service
                    change.save()

                if should_deploy_services:
                    new_deployment = DockerDeployment.objects.create(
                        service=cloned_service,
                    )
                    cloned_service.apply_pending_changes(new_deployment)

                    ports: List[int] = (
                        service.urls.filter(associated_port__isnull=False)
                        .values_list("associated_port", flat=True)
                        .distinct()
                    )  # type: ignore
                    for port in ports:
                        DeploymentURL.generate_for_deployment(
                            deployment=new_deployment,
                            service=cloned_service,
                            port=port,
                        )

                    new_deployment.service_snapshot = DockerServiceSerializer(cloned_service).data  # type: ignore
                    new_deployment.save()
                    payload = DockerDeploymentDetails.from_deployment(
                        deployment=new_deployment
                    )
                    workflows_to_run.append(
                        (DeployDockerServiceWorkflow.run, payload, payload.workflow_id)
                    )

            transaction.on_commit(
                lambda: [
                    start_workflow(
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
        if environment.name == "production":
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

        if environment.name == "production":
            raise exceptions.PermissionDenied(
                "Cannot delete the production environment"
            )

        archived_version = ArchivedProject.get_or_create_from_project(project)

        docker_service_list = (
            DockerRegistryService.objects.filter(
                Q(project=project) & Q(environment=environment)
            )
            .select_related("project", "healthcheck", "environment")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        )
        id_list = []
        for service in docker_service_list:
            if service.deployments.count() > 0:
                ArchivedDockerService.create_from_service(service, archived_version)
                id_list.append(service.id)

        PortConfiguration.objects.filter(
            Q(dockerregistryservice__id__in=id_list)
        ).delete()
        URL.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        Volume.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        Config.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        Config.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        for service in docker_service_list:
            if service.healthcheck is not None:
                service.healthcheck.delete()
        docker_service_list.delete()

        details = EnvironmentDetails(
            id=environment.id, project_id=project.id, name=environment.name
        )
        workflow_id = environment.archive_workflow_id
        transaction.on_commit(
            lambda: start_workflow(
                ArchiveEnvWorkflow.run,
                details,
                id=workflow_id,
            )
        )

        environment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
