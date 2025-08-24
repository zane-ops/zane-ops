from datetime import timedelta
import time
from typing import List, cast
from django.db import IntegrityError, transaction
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
    TriggerPreviewEnvRequestSerializer,
    UpdateEnvironmentRequestSerializer,
    PreviewEnvTemplateSerializer,
)
from ..models import (
    Project,
    Service,
    Environment,
    DeploymentChange,
    SharedEnvVariable,
    PreviewEnvTemplate,
    PreviewEnvMetadata,
    GitApp,
    CloneEnvPreviewPayload,
)
from ..serializers import (
    EnvironmentSerializer,
    EnvironmentWithVariablesSerializer,
    SharedEnvVariableSerializer,
    ErrorResponse409Serializer,
)
from temporal.client import TemporalClient, StartWorkflowArg
from temporal.workflows import (
    DeployGitServiceWorkflow,
    CreateEnvNetworkWorkflow,
    ArchiveEnvWorkflow,
    DeployDockerServiceWorkflow,
    DelayedArchiveEnvWorkflow,
)
from temporal.shared import (
    EnvironmentDetails,
    DeploymentDetails,
)
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.utils.serializer_helpers import ReturnDict
from django.utils.text import slugify
from faker import Faker
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework import serializers


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
    serializer_class = EnvironmentWithVariablesSerializer

    @extend_schema(
        request=CloneEnvironmentRequestSerializer,
        responses={
            201: EnvironmentWithVariablesSerializer,
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
            new_environment = current_environment.clone(
                env_name=name,
            )
        except IntegrityError:
            raise ResourceConflict(
                f"An environment with the name `{name}` already exists in this project"
            )
        else:
            workflows_to_run: List[StartWorkflowArg] = [
                StartWorkflowArg(
                    CreateEnvNetworkWorkflow.run,
                    EnvironmentDetails(
                        id=new_environment.id,
                        project_id=project.id,
                        name=new_environment.name,
                    ),
                    new_environment.workflow_id,
                )
            ]

            if should_deploy_services:
                for service in new_environment.services.all():
                    if service.type == Service.ServiceType.DOCKER_REGISTRY:
                        workflow = DeployDockerServiceWorkflow.run
                        new_deployment = service.prepare_new_docker_deployment()
                    else:
                        workflow = DeployGitServiceWorkflow.run
                        new_deployment = service.prepare_new_git_deployment()
                    payload = DeploymentDetails.from_deployment(
                        deployment=new_deployment
                    )
                    workflows_to_run.append(
                        StartWorkflowArg(
                            workflow,
                            payload,
                            payload.workflow_id,
                        )
                    )

            def on_commit():
                for wf in workflows_to_run:
                    TemporalClient.start_workflow(
                        wf.workflow,
                        wf.payload,
                        wf.workflow_id,
                    )

            transaction.on_commit(on_commit)

            serializer = EnvironmentWithVariablesSerializer(new_environment)
            return Response(status=status.HTTP_201_CREATED, data=serializer.data)


class EnvironmentDetailsAPIView(APIView):
    serializer_class = EnvironmentSerializer

    @extend_schema(
        responses={200: EnvironmentWithVariablesSerializer},
        operation_id="getEnvironment",
        summary="Get a single environment",
    )
    def get(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = (
                Environment.objects.filter(name=env_slug.lower(), project=project)
                .select_related("preview_metadata")
                .prefetch_related("variables")
                .get()
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )
        serializer = EnvironmentWithVariablesSerializer(environment)
        return Response(data=serializer.data)

    @extend_schema(
        request=UpdateEnvironmentRequestSerializer,
        operation_id="updateEnvironment",
        summary="Update an environment",
    )
    def patch(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = (
                Environment.objects.filter(name=env_slug.lower(), project=project)
                .select_related("preview_metadata")
                .prefetch_related("variables")
                .get()
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )
        if environment.name == Environment.PRODUCTION_ENV_NAME:
            raise exceptions.PermissionDenied(
                "Cannot rename the production environment."
            )
        elif environment.is_preview:
            raise exceptions.PermissionDenied("Cannot rename a preview environment.")

        form = UpdateEnvironmentRequestSerializer(data=request.data)
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
            environment = (
                Environment.objects.filter(name=env_slug.lower(), project=project)
                .select_related("preview_metadata")
                .prefetch_related("variables", "services")
                .get()
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )

        if environment.name == Environment.PRODUCTION_ENV_NAME:
            raise exceptions.PermissionDenied(
                "Cannot delete the production environment"
            )
        if PreviewEnvTemplate.objects.filter(base_environment=environment).count() > 0:
            raise ResourceConflict(
                "Cannot delete this environment as it is used as a base for a preview template, please delete the template first."
            )

        environment.delete_resources()

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

    def get_queryset(self):  # type: ignore
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


class TriggerPreviewEnvironmentAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "deploy_webhook"

    @transaction.atomic()
    @extend_schema(
        request=TriggerPreviewEnvRequestSerializer,
        responses={201: EnvironmentWithVariablesSerializer},
        operation_id="webhookTriggerPreviewEnv",
        summary="Webhook to trigger a new preview environment",
    )
    def post(self, request: Request, deploy_token: str):
        try:
            current_service = (
                Service.objects.filter(
                    deploy_token=deploy_token,
                    type=Service.ServiceType.GIT_REPOSITORY,
                    git_app__isnull=False,
                )
                .select_related(
                    "project",
                    "healthcheck",
                    "environment",
                    "git_app",
                    "git_app__gitlab",
                    "git_app__github",
                )
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes"
                )
            ).get()
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with a deploy_token `{deploy_token}` does not exists in this ZaneOps instance."
            )

        git_source_change = current_service.unapplied_changes.filter(
            field=DeploymentChange.ChangeField.GIT_SOURCE
        ).first()
        if (
            git_source_change is not None
            and cast(dict, git_source_change.new_value).get("git_app") is None
        ):
            raise ResourceConflict(
                detail=(
                    "The selected service has a pending change which would remove the Git app attached to it"
                    " please cancel this change before triggering the preview."
                )
            )

        project = current_service.project
        gitapp = cast(GitApp, current_service.git_app)

        form = TriggerPreviewEnvRequestSerializer(
            data=request.data,
            context={"project": project, "service": current_service},
        )
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)
        preview_branch_name = data["branch_name"]
        template_slug = data.get("template")

        if template_slug is not None:
            preview_template = (
                project.preview_templates.filter(slug=template_slug)
                .select_related("base_environment")
                .get()
            )
        else:
            preview_template = project.default_preview_template

        total_preview_env_for_template = project.environments.filter(
            is_preview=True,
            preview_metadata__template=preview_template,
        ).count()

        if total_preview_env_for_template == preview_template.preview_env_limit:
            raise exceptions.PermissionDenied(
                "You are not allowed to create a new preview environment because the limit"
                f" ({preview_template.preview_env_limit}) has been reached"
            )
        base_environment = preview_template.base_environment or project.production_env
        if base_environment.id != current_service.environment.id:
            raise ResourceConflict(
                f"Template `{preview_template.slug}` cannot be used to create a preview environment"
                " since the service is not part of its base environment."
            )

        fake = Faker()
        Faker.seed(time.monotonic())
        env_name = f"preview-{slugify(data['branch_name'])}-{fake.slug()}".lower()
        external_branch_url = None
        if gitapp.github:
            external_branch_url = (
                cast(str, current_service.repository_url).removesuffix(".git")
                + "/tree/"
                + preview_branch_name
            )
        elif gitapp.gitlab:
            external_branch_url = (
                cast(str, current_service.repository_url).removesuffix(".git")
                + "/-/tree/"
                + preview_branch_name
            )

        preview_commit_sha = data["commit_sha"]
        preview_metadata = PreviewEnvMetadata.objects.create(
            branch_name=preview_branch_name,
            commit_sha=preview_commit_sha,
            source_trigger=Environment.PreviewSourceTrigger.API,
            service=current_service,
            template=preview_template,
            auto_teardown=preview_template.auto_teardown,
            external_url=external_branch_url,
            git_app=gitapp,
            repository_url=current_service.repository_url,
            ttl_seconds=preview_template.ttl_seconds,
            auth_enabled=preview_template.auth_enabled,
            auth_user=preview_template.auth_user,
            auth_password=preview_template.auth_password,
            deploy_state=PreviewEnvMetadata.PreviewDeployState.APPROVED,
        )

        new_environment = base_environment.clone(
            env_name=env_name,
            payload=CloneEnvPreviewPayload(
                template=preview_template, metadata=preview_metadata
            ),
        )
        workflows_to_run: List[StartWorkflowArg] = [
            StartWorkflowArg(
                CreateEnvNetworkWorkflow.run,
                EnvironmentDetails(
                    id=new_environment.id,
                    project_id=project.id,
                    name=new_environment.name,
                ),
                new_environment.workflow_id,
            )
        ]

        for service in new_environment.services.all():
            if service.type == Service.ServiceType.DOCKER_REGISTRY:
                workflow = DeployDockerServiceWorkflow.run
                new_deployment = service.prepare_new_docker_deployment()
            else:
                workflow = DeployGitServiceWorkflow.run
                new_deployment = service.prepare_new_git_deployment()

            payload = DeploymentDetails.from_deployment(deployment=new_deployment)
            workflows_to_run.append(
                StartWorkflowArg(
                    workflow,
                    payload,
                    payload.workflow_id,
                )
            )

        if preview_template.ttl_seconds is not None:
            workflows_to_run.append(
                StartWorkflowArg(
                    workflow=DelayedArchiveEnvWorkflow.run,
                    payload=EnvironmentDetails(
                        id=new_environment.id,
                        project_id=new_environment.project.id,
                        name=new_environment.name,
                    ),
                    workflow_id=new_environment.delayed_archive_workflow_id,
                    start_delay=timedelta(seconds=preview_template.ttl_seconds),
                )
            )

        def on_commit():
            for wf in workflows_to_run:
                TemporalClient.start_workflow(
                    workflow=wf.workflow,
                    arg=wf.payload,
                    id=wf.workflow_id,
                    start_delay=wf.start_delay,
                )

        transaction.on_commit(on_commit)

        serializer = EnvironmentWithVariablesSerializer(new_environment)
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


class PreviewEnvTemplateListAPIView(ListCreateAPIView):
    serializer_class = PreviewEnvTemplateSerializer
    pagination_class = None
    queryset = (
        PreviewEnvTemplate.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    def get_queryset(self):  # type: ignore
        project_slug = self.kwargs["slug"]

        try:
            project = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            raise exceptions.NotFound("This project does not exist")

        return (
            project.preview_templates.select_related(
                "base_environment",
                "project",
            )
            .prefetch_related("variables", "services_to_clone")
            .order_by("id")
        )

    def perform_create(self, serializer: serializers.ModelSerializer):
        project_slug = self.kwargs["slug"]
        project = Project.objects.get(slug=project_slug)
        serializer.save(project=project)

    @transaction.atomic()
    def post(self, request: Request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PreviewEnvTemplateDetailsAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = PreviewEnvTemplateSerializer
    lookup_url_kwarg = (
        "template_slug"  # This corresponds to the param in the URL configuration
    )
    queryset = (
        PreviewEnvTemplate.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_object`
    http_method_names = ["patch", "get", "delete"]

    def get_serializer(self, *args, **kwargs):
        try:
            serializer = super().get_serializer(*args, **kwargs)
            serializer.context["instance"] = self.get_object()
        except Exception:
            serializer = super().get_serializer(*args, **kwargs)
        return serializer

    def get_object(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        template_slug = self.kwargs["template_slug"]

        try:
            project = Project.objects.get(slug=project_slug)
            template = (
                project.preview_templates.filter(slug=template_slug)
                .select_related("base_environment", "project")
                .prefetch_related("variables", "services_to_clone")
                .get()
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound("This project does not exist")
        except PreviewEnvTemplate.DoesNotExist:
            raise exceptions.NotFound(
                f"The preview template with the slug `{template_slug}` does not exist in this project"
            )

        return template

    def perform_destroy(self, instance: PreviewEnvTemplate):
        if instance.is_default:
            raise ResourceConflict("Cannot delete the default preview template")
        if instance.preview_metas.count() > 0:
            raise ResourceConflict(
                "Cannot delete this preview template as it is used for at least one preview environment,"
                " please delete the preview environments using this template first."
            )
        return super().perform_destroy(instance)

    @transaction.atomic()
    def patch(self, request: Request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @transaction.atomic()
    def delete(self, request: Request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
