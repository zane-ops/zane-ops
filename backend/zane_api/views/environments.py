from datetime import timedelta
import time
from typing import List, cast
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
import requests
from rest_framework import exceptions
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import ResourceConflict, BadRequest
from .serializers import (
    CreateEnvironmentRequestSerializer,
    CloneEnvironmentRequestSerializer,
    TriggerPreviewEnvRequestSerializer,
    UpdateEnvironmentRequestSerializer,
    PreviewEnvTemplateSerializer,
    ReviewPreviewEnvDeploymentRequestSerializer,
    PreviewEnvDeployDecision,
)
from ..models import (
    Project,
    Service,
    Environment,
    Deployment,
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
    DeployComposeStackWorkflow,
)
from temporal.shared import (
    EnvironmentDetails,
    DeploymentDetails,
    ComposeStackDeploymentDetails,
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

        data = cast(dict, form.data)
        name = data["name"].lower()
        should_deploy = data["deploy_after_clone"]
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

            if should_deploy:
                for stack in new_environment.compose_stacks.all():
                    deployment = stack.deployments.create(
                        commit_message="Deploy from clone",
                    )
                    stack.apply_pending_changes(deployment)

                    deployment.stack_snapshot = stack.snapshot.to_dict()  # type: ignore
                    deployment.save()

                    payload = ComposeStackDeploymentDetails.from_deployment(deployment)
                    workflows_to_run.append(
                        StartWorkflowArg(
                            DeployComposeStackWorkflow.run,
                            payload,
                            payload.workflow_id,
                        )
                    )
                    pass
                for service in new_environment.services.all():
                    if service.type == Service.ServiceType.DOCKER_REGISTRY:
                        workflow = DeployDockerServiceWorkflow.run
                        new_deployment = service.prepare_new_docker_deployment(
                            commit_message="Clone deployment"
                        )
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


class ReviewPreviewEnvDeployAPIView(APIView):
    @extend_schema(
        responses={200: EnvironmentWithVariablesSerializer},
        operation_id="getPreviewEnvToReview",
        summary="Get the preview deployment",
    )
    def get(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = (
                Environment.objects.filter(
                    name=env_slug.lower(),
                    project=project,
                    is_preview=True,
                    preview_metadata__deploy_state=PreviewEnvMetadata.PreviewDeployState.PENDING,
                )
                .select_related(
                    "preview_metadata",
                    "preview_metadata__service",
                    "preview_metadata__git_app",
                )
                .prefetch_related("variables")
                .get()
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A pending preview env with the slug `{env_slug}` does not exist in this project"
            )

        serializer = EnvironmentWithVariablesSerializer(environment)
        return Response(data=serializer.data)

    @extend_schema(
        responses={204: None},
        request=ReviewPreviewEnvDeploymentRequestSerializer,
        operation_id="reviewPreviewEnvDeploy",
        summary="Approve or Decline the execution of the deployment of a preview environment",
    )
    @transaction.atomic()
    def post(self, request: Request, slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = (
                Environment.objects.filter(
                    name=env_slug.lower(),
                    project=project,
                    is_preview=True,
                    preview_metadata__deploy_state=PreviewEnvMetadata.PreviewDeployState.PENDING,
                )
                .select_related(
                    "preview_metadata",
                    "preview_metadata__template",
                    "preview_metadata__git_app",
                    "preview_metadata__git_app__github",
                    "preview_metadata__git_app__gitlab",
                )
                .prefetch_related("variables")
                .get()
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A pending preview env with the slug `{env_slug}` does not exist in this project"
            )

        form = ReviewPreviewEnvDeploymentRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        preview_meta = cast(PreviewEnvMetadata, environment.preview_metadata)

        workflows_to_run: List[StartWorkflowArg] = []
        match data["decision"]:
            case PreviewEnvDeployDecision.APPROVE:
                preview_meta.deploy_state = (
                    PreviewEnvMetadata.PreviewDeployState.APPROVED
                )
                preview_meta.save()

                workflows_to_run.append(
                    StartWorkflowArg(
                        workflow=CreateEnvNetworkWorkflow.run,
                        payload=EnvironmentDetails(
                            id=environment.id,
                            project_id=project.id,
                            name=environment.name,
                        ),
                        workflow_id=environment.workflow_id,
                    )
                )

                for service in environment.services.all():
                    if service.type == Service.ServiceType.DOCKER_REGISTRY:
                        new_deployment = service.prepare_new_docker_deployment(
                            trigger_method=Deployment.DeploymentTriggerMethod.AUTO
                        )
                    else:
                        new_deployment = service.prepare_new_git_deployment(
                            trigger_method=Deployment.DeploymentTriggerMethod.AUTO
                        )

                    payload = DeploymentDetails.from_deployment(
                        deployment=new_deployment
                    )
                    workflows_to_run.append(
                        StartWorkflowArg(
                            workflow=(
                                DeployDockerServiceWorkflow.run
                                if service.type == Service.ServiceType.DOCKER_REGISTRY
                                else DeployGitServiceWorkflow.run
                            ),
                            payload=payload,
                            workflow_id=payload.workflow_id,
                        )
                    )

                    if preview_meta.template.ttl_seconds is not None:
                        workflows_to_run.append(
                            StartWorkflowArg(
                                workflow=DelayedArchiveEnvWorkflow.run,
                                payload=EnvironmentDetails(
                                    id=environment.id,
                                    project_id=environment.project.id,
                                    name=environment.name,
                                ),
                                workflow_id=environment.delayed_archive_workflow_id,
                                start_delay=timedelta(
                                    seconds=preview_meta.template.ttl_seconds
                                ),
                            )
                        )
            case PreviewEnvDeployDecision.DECLINE:
                cloned_service = preview_meta.environment.services.filter(
                    network_alias=preview_meta.service.network_alias
                ).first()

                if (
                    preview_meta.pr_comment_id is not None
                    and cloned_service is not None
                    and preview_meta.pr_base_repo_url is not None
                ):
                    if preview_meta.git_app.github is not None:
                        headers = {
                            "Authorization": f"Bearer {preview_meta.git_app.github.get_access_token()}",
                            "Accept": "application/vnd.github+json",
                        }
                        payload = {
                            "body": preview_meta.get_pull_request_deployment_declined_comment_body(
                                cloned_service
                            )
                        }
                        repo_url = preview_meta.pr_base_repo_url.removesuffix(".git")
                        repo_full_name = repo_url.removeprefix(
                            "https://github.com/"
                        ).removesuffix(".git")
                        owner, repo = repo_full_name.split("/")
                        url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{preview_meta.pr_comment_id}"
                        # Try to make request to update comment (we ignore the response status)
                        response = requests.patch(url, headers=headers, json=payload)
                        if not status.is_success(response.status_code):
                            text = response.text
                            print(
                                f"Error when trying to upser a PR comment for {preview_meta.service.slug=} on the PR #{preview_meta.pr_number}({repo_url}/pulls/{preview_meta.pr_number}): ",
                                response.status_code,
                                text,
                                f"{url=}",
                            )
                workflows_to_run.append(
                    StartWorkflowArg(
                        workflow=ArchiveEnvWorkflow.run,
                        payload=EnvironmentDetails.from_environment(environment),
                        workflow_id=environment.archive_workflow_id,
                    )
                )

                environment.delete_resources()
                environment.delete()

        def on_commit():
            for wf in workflows_to_run:
                TemporalClient.start_workflow(
                    workflow=wf.workflow,
                    arg=wf.payload,
                    id=wf.workflow_id,
                    start_delay=wf.start_delay,
                )

        transaction.on_commit(on_commit)
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        details = EnvironmentDetails.from_environment(environment)
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
    queryset = SharedEnvVariable.objects.all()  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

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
        preview_branch_name = data.get("branch_name")
        preview_pr_number = data.get("pr_number")

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
                f"of {preview_template.preview_env_limit} preview envs for this preview template has been reached"
            )
        base_environment = preview_template.base_environment or project.production_env
        if base_environment.id != current_service.environment.id:
            raise ResourceConflict(
                f"Template `{preview_template.slug}` cannot be used to create a preview environment"
                " since the service is not part of its base environment."
            )

        fake = Faker()
        Faker.seed(time.monotonic())
        should_deploy = True

        if preview_branch_name is not None:
            env_name = f"preview-{slugify(preview_branch_name)}-{fake.slug()}".lower()
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
                head_repository_url=current_service.repository_url,
                ttl_seconds=preview_template.ttl_seconds,
                auth_enabled=preview_template.auth_enabled,
                auth_user=preview_template.auth_user,
                auth_password=preview_template.auth_password,
                deploy_state=PreviewEnvMetadata.PreviewDeployState.APPROVED,
            )

            new_environment = base_environment.clone(
                env_name=env_name,
                preview_data=CloneEnvPreviewPayload(
                    template=preview_template, metadata=preview_metadata
                ),
            )
        elif preview_pr_number is not None:
            if gitapp.github:
                github = gitapp.github
                # Get existing pull request
                base_url = "https://api.github.com/repos"
                repo_full_path = (
                    cast(str, current_service.repository_url)
                    .removeprefix("https://github.com")
                    .removesuffix(".git")
                )
                url = base_url + repo_full_path + f"/pulls/{preview_pr_number}"
                headers = {
                    "Authorization": f"Bearer {github.get_access_token()}",
                    "Accept": "application/vnd.github+json",
                }
                response = requests.get(url, headers=headers)
                if response.status_code != status.HTTP_200_OK:
                    raise BadRequest(
                        f"Pull Request with number `{preview_pr_number}` does not exists does not exists on repo `{current_service.repository_url}`"
                    )
                pull_request = response.json()

                branch_name = pull_request["head"]["ref"]
                is_fork = pull_request["head"]["repo"]["fork"]
                should_deploy = not is_fork

                base_repository_url = f"https://github.com/{pull_request['base']['repo']['full_name']}.git"
                head_repository_url = f"https://github.com/{pull_request['head']['repo']['full_name']}.git"

                env_name = f"preview-pr-{pull_request['number']}-{current_service.slug}-{fake.slug()}".lower()
                preview_meta = PreviewEnvMetadata.objects.create(
                    branch_name=branch_name,
                    source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                    service=current_service,
                    template=preview_template,
                    auto_teardown=preview_template.auto_teardown,
                    external_url=pull_request["html_url"],
                    git_app=gitapp,
                    head_repository_url=head_repository_url,
                    ttl_seconds=preview_template.ttl_seconds,
                    auth_enabled=preview_template.auth_enabled,
                    auth_user=preview_template.auth_user,
                    pr_author=pull_request["user"]["login"],
                    pr_base_repo_url=base_repository_url,
                    pr_base_branch_name=pull_request["base"]["ref"],
                    auth_password=preview_template.auth_password,
                    deploy_state=(
                        PreviewEnvMetadata.PreviewDeployState.PENDING
                        if is_fork
                        else PreviewEnvMetadata.PreviewDeployState.APPROVED
                    ),
                    pr_number=pull_request["number"],
                    pr_title=pull_request["title"],
                )

                base_environment = cast(Environment, preview_template.base_environment)

                new_environment = base_environment.clone(
                    env_name=env_name,
                    preview_data=CloneEnvPreviewPayload(
                        template=preview_template, metadata=preview_meta
                    ),
                )
                if is_fork:
                    cloned_service = new_environment.services.get(
                        slug=current_service.slug
                    )
                    # 1️⃣ Define the API endpoint for creating a comment
                    owner, repo = repo_full_path.split("/")
                    issue_number = pull_request["number"]  # issue or PR number

                    # create issue comment
                    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"

                    # 2️⃣ Prepare the request
                    headers = {
                        "Authorization": f"Bearer {github.get_access_token()}",
                        "Accept": "application/vnd.github+json",
                    }
                    payload = {
                        "body": preview_meta.get_pull_request_deployment_blocked_comment_body(
                            cloned_service
                        )
                    }

                    # 3️⃣ Make the POST request
                    response = requests.post(url, headers=headers, json=payload)
                    # 4️⃣ Check the response
                    if response.status_code == status.HTTP_201_CREATED:
                        data = response.json()
                        print(
                            "Comment created:",
                            data["html_url"],
                        )
                        print("Comment Body:\n", data["body"])

                        # Update Preview metadata with the comment ID
                        preview_meta.pr_comment_id = data["id"]
                        preview_meta.save()
                    else:
                        print(
                            f"Error when trying to create a PR comment for the {preview_meta.service=} on the PR #{pull_request['number']}({pull_request['html_url']}): ",
                            response.status_code,
                            response.text,
                        )
            else:
                raise NotImplementedError(
                    "Specifying the Pull Request number is only supported for github apps right now"
                )
        else:
            raise NotImplementedError("This code should be unreacheable")

        # add env vars
        for env in data["env_variables"]:
            new_environment.variables.update_or_create(
                key=env["key"],
                defaults={"value": env["value"]},
            )

        workflows_to_run: List[StartWorkflowArg] = []
        if should_deploy:
            workflows_to_run = [
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
                    new_deployment = service.prepare_new_docker_deployment(
                        trigger_method=Deployment.DeploymentTriggerMethod.API
                    )
                else:
                    workflow = DeployGitServiceWorkflow.run
                    new_deployment = service.prepare_new_git_deployment(
                        trigger_method=Deployment.DeploymentTriggerMethod.API
                    )

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
    queryset = PreviewEnvTemplate.objects.all()  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

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
    queryset = PreviewEnvTemplate.objects.all()  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_object`
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
