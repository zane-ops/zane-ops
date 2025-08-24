from datetime import timedelta
import time
from typing import List, cast
from faker import Faker
import requests
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from ..serializers import (
    GithubWebhookEventSerializer,
    SetupGithubAppQuerySerializer,
    GithubAppSerializer,
    GithubWebhookPingRequestSerializer,
    GithubWebhookInstallationRequestSerializer,
    GithubWebhookEvent,
    GithubWebhookInstallationRepositoriesRequestSerializer,
    GithubWebhookPushRequestSerializer,
    GithubWebhookPullRequestSerializer,
)
from drf_spectacular.utils import extend_schema, inline_serializer

from zane_api.views import BadRequest
from django.conf import settings

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status, serializers
from zane_api.models import (
    GitApp,
    Service,
    Environment,
    Deployment,
    PreviewEnvMetadata,
    CloneEnvPreviewPayload,
)
from ..models import GitHubApp, GitRepository
from temporal.shared import DeploymentDetails, EnvironmentDetails
from temporal.client import TemporalClient, StartWorkflowArg, SignalWorkflowArg
from temporal.workflows import (
    DeployGitServiceWorkflow,
    CancelDeploymentSignalInput,
    ArchiveEnvWorkflow,
    CreateEnvNetworkWorkflow,
    DeployDockerServiceWorkflow,
    DelayedArchiveEnvWorkflow,
)
from ..dtos import GitCommitInfo
from zane_api.utils import jprint


class SetupGithubAppAPIView(APIView):

    @transaction.atomic()
    @extend_schema(
        responses={status.HTTP_303_SEE_OTHER: None},
        operation_id="setupGithubApp",
        summary="setup github app",
        parameters=[SetupGithubAppQuerySerializer],
    )
    def get(self, request: Request):
        form = SetupGithubAppQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        code = data["code"]
        state = data["state"]
        match state:
            case state if isinstance(state, str) and state.startswith("install"):
                _, app_id = state.split(":")
                installation_id: int = data["installation_id"]

                try:
                    git_app = (
                        GitApp.objects.filter(github__id=app_id)
                        .select_related("github")
                        .get()
                    )
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        f"Github app with id {app_id} does not exist"
                    )

                gh_app: GitHubApp = cast(GitHubApp, git_app.github)
                gh_app.installation_id = installation_id
                gh_app.save()

            case "create":
                url = f"https://api.github.com/app-manifests/{code}/conversions"
                headers = {
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                response = requests.post(url, headers=headers)

                if not status.is_success(response.status_code):
                    raise BadRequest("invalid Github app installation code")

                github_manifest_data = response.json()

                github_app = GitHubApp.objects.filter(
                    app_id=github_manifest_data["id"]
                ).first()

                if github_app is None:
                    github_app = GitHubApp.objects.create(
                        app_id=github_manifest_data["id"],
                        client_id=github_manifest_data["client_id"],
                        client_secret=github_manifest_data["client_secret"],
                        webhook_secret=github_manifest_data["webhook_secret"],
                        app_url=github_manifest_data["html_url"],
                        private_key=github_manifest_data["pem"],
                        name=github_manifest_data["name"],
                    )

                git_app, _ = GitApp.objects.get_or_create(github=github_app)
            case _:
                raise BadRequest("Invalid state token")

        base_url = ""
        if settings.ENVIRONMENT != settings.PRODUCTION_ENV:
            base_url = "http://localhost:5173"

        return Response(
            headers={"Location": f"{base_url}/settings/git-apps"},
            status=status.HTTP_303_SEE_OTHER,
        )


class GithubAppDetailsAPIView(RetrieveUpdateAPIView):
    serializer_class = GithubAppSerializer
    queryset = GitHubApp.objects.all()
    lookup_field = "id"
    http_method_names = ["patch", "get"]


class TestGithubAppAPIView(APIView):
    @extend_schema(
        responses={
            200: inline_serializer(
                "TestGithubAppResponseSerializer",
                fields={"repositories_count": serializers.IntegerField()},
            ),
        },
        operation_id="testGithubApp",
    )
    def get(self, request: Request, id: str):
        try:
            git_app = (
                GitApp.objects.filter(github__id=id).select_related("github").get()
            )
        except GitApp.DoesNotExist:
            raise exceptions.NotFound(f"Github app with id {id} does not exist")

        github_app: GitHubApp = git_app.github  # type: ignore
        access_token = github_app.get_access_token()
        url = "https://api.github.com/installation/repositories"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = requests.get(url, headers=headers)
        if not status.is_success(response.status_code):
            raise BadRequest(
                "This github app may not be correctly installed or it has been deleted on github"
            )

        result = response.json()

        return Response(
            data={
                "repositories_count": result["total_count"],
            }
        )


@extend_schema(exclude=True)
class GithubWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gitapp_webhook"

    @transaction.atomic()
    def post(self, request: Request):
        request_body: bytes = request.body
        request_data = request.data
        form = GithubWebhookEventSerializer(
            data={
                "event": request.headers.get("x-github-event"),
                "signature256": request.headers.get("x-hub-signature-256"),
            }
        )
        form.is_valid(raise_exception=True)
        event = cast(ReturnDict, form.data)["event"]
        signature = cast(ReturnDict, form.data)["signature256"]
        event_serializer_map = {
            GithubWebhookEvent.PING: GithubWebhookPingRequestSerializer,
            GithubWebhookEvent.INSTALLATION: GithubWebhookInstallationRequestSerializer,
            GithubWebhookEvent.INSTALLATION_REPOS: GithubWebhookInstallationRepositoriesRequestSerializer,
            GithubWebhookEvent.PUSH: GithubWebhookPushRequestSerializer,
            GithubWebhookEvent.PULL_REQUEST: GithubWebhookPullRequestSerializer,
        }

        serializer_class = event_serializer_map[event]
        form = serializer_class(data=request_data)
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        match form:
            case GithubWebhookPingRequestSerializer():
                try:
                    gitapp = GitApp.objects.get(github__app_id=data["hook"]["app_id"])
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )
                github = cast(GitHubApp, gitapp.github)
                verified = github.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")
            case GithubWebhookInstallationRequestSerializer():
                try:
                    gitapp = GitApp.objects.get(
                        github__app_id=data["installation"]["app_id"]
                    )
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )
                github = cast(GitHubApp, gitapp.github)
                verified = github.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")

                repositories = data["repositories"]

                def map_repository(repository: dict[str, str]):
                    return GitRepository(
                        path=repository["full_name"],
                        url=f"https://github.com/{repository["full_name"]}.git",
                        private=repository["private"],
                    )

                mapped = [map_repository(repo) for repo in repositories]
                github.add_repositories(mapped)
            case GithubWebhookInstallationRepositoriesRequestSerializer():
                try:
                    gitapp = GitApp.objects.get(
                        github__app_id=data["installation"]["app_id"]
                    )
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )
                github = cast(GitHubApp, gitapp.github)
                verified = github.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")

                repositories_added = data["repositories_added"]
                repositories_removed = data["repositories_removed"]

                if len(repositories_added) > 0:

                    def map_repository(repository: dict[str, str]):
                        return GitRepository(
                            path=repository["full_name"],
                            url=f"https://github.com/{repository["full_name"]}.git",
                            private=repository["private"],
                        )

                    mapped = [map_repository(repo) for repo in repositories_added]
                    github.add_repositories(mapped)
                if len(repositories_removed) > 0:
                    repos_to_delete = github.repositories.filter(
                        url__in=[
                            f"https://github.com/{repo["full_name"]}.git"
                            for repo in repositories_removed
                        ]
                    )
                    # detach the relations between the repos and this app
                    github.repositories.remove(*repos_to_delete)

                    # cleanup orphan repositories
                    GitRepository.objects.filter(
                        gitlabapps__isnull=True, githubapps__isnull=True
                    ).delete()
            case GithubWebhookPushRequestSerializer():
                try:
                    gitapp = GitApp.objects.get(
                        github__installation_id=data["installation"]["id"]
                    )
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )
                github = cast(GitHubApp, gitapp.github)
                verified = github.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")

                ref: str = data["ref"]
                head_commit: dict | None = data["head_commit"]
                branch_deleted = data["deleted"]
                # We only consider pushes to a branch
                # we ignore tags and other push events
                if ref.startswith("refs/heads/"):
                    branch_name = ref.replace("refs/heads/", "")
                    repository_url = (
                        f"https://github.com/{data["repository"]["full_name"]}.git"
                    )
                    if branch_deleted:
                        environment_delete_payload: list[
                            tuple[EnvironmentDetails, str]
                        ] = []
                        matching_preview_envs = Environment.objects.filter(
                            is_preview=True,
                            preview_metadata__source_trigger=Environment.PreviewSourceTrigger.API,
                            preview_metadata__repository_url=repository_url,
                            preview_metadata__git_app=gitapp,
                            preview_metadata__branch_name=branch_name,
                            preview_metadata__auto_teardown=True,
                        ).select_related("project", "preview_metadata")
                        for environment in matching_preview_envs:
                            environment_delete_payload.append(
                                (
                                    EnvironmentDetails(
                                        id=environment.id,
                                        project_id=environment.project.id,
                                        name=environment.name,
                                    ),
                                    environment.archive_workflow_id,
                                )
                            )
                            environment.delete_resources()
                            environment.delete()

                        def on_commit():
                            for details, workflow_id in environment_delete_payload:
                                TemporalClient.start_workflow(
                                    ArchiveEnvWorkflow.run,
                                    details,
                                    id=workflow_id,
                                )

                        transaction.on_commit(on_commit)
                    else:
                        affected_services = (
                            Service.get_services_triggered_by_push_event(
                                gitapp=gitapp,
                                branch_name=branch_name,
                                repository_url=repository_url,
                            )
                        )

                        deployments_to_cancel: list[Deployment] = []
                        payloads_for_workflows_to_run: list[DeploymentDetails] = []
                        changed_paths: set[str] = set()
                        for commit in data["commits"]:
                            changed_paths.update(
                                commit["added"],
                                commit["removed"],
                                commit["modified"],
                            )

                        for service in affected_services:
                            # ignore service that don't match the paths
                            if not service.match_paths(changed_paths):
                                continue

                            if service.cleanup_queue_on_auto_deploy:
                                deployments_to_cancel.extend(
                                    Deployment.flag_deployments_for_cancellation(
                                        service, include_running_deployments=True
                                    )
                                )
                            commit = (
                                GitCommitInfo(
                                    sha=head_commit["id"],
                                    message=head_commit["message"],
                                    author_name=head_commit["author"]["name"],
                                )
                                if head_commit is not None
                                else None
                            )
                            new_deployment = service.prepare_new_git_deployment(
                                commit=commit,
                                trigger_method=Deployment.DeploymentTriggerMethod.AUTO,
                            )

                            payloads_for_workflows_to_run.append(
                                DeploymentDetails.from_deployment(
                                    deployment=new_deployment
                                )
                            )

                        def commit_callback():
                            for dpl in deployments_to_cancel:
                                TemporalClient.workflow_signal(
                                    workflow=DeployGitServiceWorkflow.run,
                                    input=CancelDeploymentSignalInput(
                                        deployment_hash=dpl.hash
                                    ),
                                    signal=DeployGitServiceWorkflow.cancel_deployment,  # type: ignore
                                    workflow_id=dpl.workflow_id,
                                )
                            for payload in payloads_for_workflows_to_run:
                                TemporalClient.start_workflow(
                                    workflow=DeployGitServiceWorkflow.run,
                                    arg=payload,
                                    id=payload.workflow_id,
                                )

                        transaction.on_commit(commit_callback)

            case GithubWebhookPullRequestSerializer():
                try:
                    gitapp = GitApp.objects.get(
                        github__installation_id=data["installation"]["id"]
                    )
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )
                github = cast(GitHubApp, gitapp.github)
                verified = github.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")

                # We only consider pushes to a branch
                # we ignore tags and other push events
                pull_request = data["pull_request"]
                branch_name = pull_request["head"]["ref"]
                repository_url = (
                    f"https://github.com/{data["repository"]["full_name"]}.git"
                )
                pull_request_source_repo_url = f"https://github.com/{pull_request["head"]['repo']["full_name"]}.git"
                workflows_to_run: List[StartWorkflowArg] = []
                workflows_signals: List[SignalWorkflowArg] = []

                match data["action"]:
                    case "opened":
                        affected_services = (
                            Service.get_services_triggered_by_pull_request_event(
                                gitapp=gitapp,
                                repository_url=repository_url,
                            )
                        )

                        for current_service in affected_services:
                            existing_preview_envs_count = (
                                Environment.objects.filter(
                                    is_preview=True,
                                    preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                                    preview_metadata__repository_url=pull_request_source_repo_url,
                                    preview_metadata__service=current_service,
                                    preview_metadata__git_app=gitapp,
                                    preview_metadata__pr_number=pull_request["number"],
                                )
                                .select_related("project", "preview_metadata")
                                .count()
                            )

                            if existing_preview_envs_count > 0:
                                # ignored because the env already exist
                                continue

                            project = current_service.project
                            preview_template = project.default_preview_template

                            total_preview_env_for_template = (
                                project.environments.filter(
                                    is_preview=True,
                                    preview_metadata__template=preview_template,
                                ).count()
                            )
                            if (
                                total_preview_env_for_template
                                == preview_template.preview_env_limit
                            ):
                                continue  # ignore if we get to the limit of max previews

                            fake = Faker()
                            Faker.seed(time.monotonic())
                            env_name = f"preview-pr-{pull_request['number']}-{current_service.slug}-{fake.slug()}".lower()
                            preview_meta = PreviewEnvMetadata.objects.create(
                                branch_name=branch_name,
                                source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                                service=current_service,
                                template=preview_template,
                                auto_teardown=preview_template.auto_teardown,
                                external_url=pull_request["html_url"],
                                git_app=gitapp,
                                repository_url=pull_request_source_repo_url,
                                ttl_seconds=preview_template.ttl_seconds,
                                auth_enabled=preview_template.auth_enabled,
                                auth_user=preview_template.auth_user,
                                auth_password=preview_template.auth_password,
                                deploy_state=PreviewEnvMetadata.PreviewDeployState.APPROVED,
                                pr_number=pull_request["number"],
                                pr_title=pull_request["title"],
                            )

                            base_environment = cast(
                                Environment, preview_template.base_environment
                            )

                            new_environment = base_environment.clone(
                                env_name=env_name,
                                payload=CloneEnvPreviewPayload(
                                    template=preview_template, metadata=preview_meta
                                ),
                            )

                            workflows_to_run.append(
                                StartWorkflowArg(
                                    workflow=CreateEnvNetworkWorkflow.run,
                                    payload=EnvironmentDetails(
                                        id=new_environment.id,
                                        project_id=project.id,
                                        name=new_environment.name,
                                    ),
                                    workflow_id=new_environment.workflow_id,
                                )
                            )

                            for service in new_environment.services.all():
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
                                            if service.type
                                            == Service.ServiceType.DOCKER_REGISTRY
                                            else DeployGitServiceWorkflow.run
                                        ),
                                        payload=payload,
                                        workflow_id=payload.workflow_id,
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
                                        start_delay=timedelta(
                                            seconds=preview_template.ttl_seconds
                                        ),
                                    )
                                )
                    case "synchronize" if pull_request["state"] == "open":
                        affected_services = (
                            Service.get_services_triggered_by_pull_request_sync_event(
                                gitapp=gitapp,
                                repository_url=repository_url,
                                pr_number=pull_request["number"],
                            )
                        )

                        deployments_to_cancel: list[Deployment] = []
                        payloads_for_workflows_to_run: list[DeploymentDetails] = []
                        for service in affected_services:
                            if service.cleanup_queue_on_auto_deploy:
                                deployments_to_cancel.extend(
                                    Deployment.flag_deployments_for_cancellation(
                                        service, include_running_deployments=True
                                    )
                                )
                            new_deployment = service.prepare_new_git_deployment(
                                trigger_method=Deployment.DeploymentTriggerMethod.AUTO,
                            )

                            payloads_for_workflows_to_run.append(
                                DeploymentDetails.from_deployment(
                                    deployment=new_deployment
                                )
                            )

                        print(f"ALL OUT PAYLOADS {payloads_for_workflows_to_run=}")

                        for dpl in deployments_to_cancel:
                            workflows_signals.append(
                                SignalWorkflowArg(
                                    workflow=DeployGitServiceWorkflow.run,
                                    input=CancelDeploymentSignalInput(
                                        deployment_hash=dpl.hash
                                    ),
                                    signal=DeployGitServiceWorkflow.cancel_deployment,  # type: ignore
                                    workflow_id=dpl.workflow_id,
                                )
                            )

                        for payload in payloads_for_workflows_to_run:
                            workflows_to_run.append(
                                StartWorkflowArg(
                                    workflow=DeployGitServiceWorkflow.run,
                                    payload=payload,
                                    workflow_id=payload.workflow_id,
                                )
                            )
                    case "closed":
                        matching_preview_envs = Environment.objects.filter(
                            is_preview=True,
                            preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                            preview_metadata__repository_url=pull_request_source_repo_url,
                            preview_metadata__git_app=gitapp,
                            preview_metadata__branch_name=branch_name,
                            preview_metadata__auto_teardown=True,
                            preview_metadata__pr_number=pull_request["number"],
                        ).select_related("project", "preview_metadata")

                        for environment in matching_preview_envs:
                            workflows_to_run.append(
                                StartWorkflowArg(
                                    workflow=ArchiveEnvWorkflow.run,
                                    payload=EnvironmentDetails(
                                        id=environment.id,
                                        project_id=environment.project.id,
                                        name=environment.name,
                                    ),
                                    workflow_id=environment.archive_workflow_id,
                                )
                            )
                            environment.delete_resources()
                            environment.delete()
                    case "edited":
                        matching_preview_envs = Environment.objects.filter(
                            is_preview=True,
                            preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                            preview_metadata__repository_url=pull_request_source_repo_url,
                            preview_metadata__git_app=gitapp,
                            preview_metadata__branch_name=branch_name,
                            preview_metadata__auto_teardown=True,
                            preview_metadata__pr_number=pull_request["number"],
                        ).select_related("project", "preview_metadata")

                        for environment in matching_preview_envs:
                            preview_metadata = cast(
                                PreviewEnvMetadata, environment.preview_metadata
                            )
                            preview_metadata.pr_title = pull_request["title"]
                            preview_metadata.save()

                    case _:
                        # no need to implement other cases
                        pass

                def on_commit():
                    for signal in workflows_signals:
                        TemporalClient.workflow_signal(
                            workflow=signal.workflow,
                            input=signal.input,
                            signal=signal.signal,  # type: ignore
                            workflow_id=signal.workflow_id,
                        )
                    for wf in workflows_to_run:
                        TemporalClient.start_workflow(
                            workflow=wf.workflow,
                            arg=wf.payload,
                            id=wf.workflow_id,
                            start_delay=wf.start_delay,
                        )

                transaction.on_commit(on_commit)

            case _:
                raise BadRequest("bad request")

        return Response(data={"success": True})
