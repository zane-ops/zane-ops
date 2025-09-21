from datetime import timedelta
import time
from typing import List, cast
from urllib.parse import urlencode, urlparse
import requests
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from rest_framework import exceptions
from ..serializers import (
    CreateGitlabAppRequestSerializer,
    CreateGitlabAppResponseSerializer,
    GitlabAppUpdateRequestSerializer,
    GitlabAppUpdateResponseSerializer,
    SetupGitlabAppQuerySerializer,
    GitlabAppSerializer,
    GitlabWebhookEventSerializer,
    GitlabWebhookPushEventRequestSerializer,
    GitlabWebhookEvent,
    GitlabWebhookMergeRequestEventRequestSerializer,
)
from faker import Faker
from drf_spectacular.utils import extend_schema, inline_serializer

from zane_api.views import BadRequest
from django.conf import settings
from temporal.client import TemporalClient, StartWorkflowArg, SignalWorkflowArg
from temporal.workflows import (
    CreateEnvNetworkWorkflow,
    DeployDockerServiceWorkflow,
    DeployGitServiceWorkflow,
    DelayedArchiveEnvWorkflow,
)

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status, serializers
from zane_api.models import (
    GitApp,
    Service,
    Deployment,
    Environment,
    PreviewEnvMetadata,
    CloneEnvPreviewPayload,
)
from ..models import GitlabApp
from django.core.cache import cache
from zane_api.utils import generate_random_chars
from rest_framework import permissions
from rest_framework.throttling import ScopedRateThrottle
from temporal.shared import (
    DeploymentDetails,
    CancelDeploymentSignalInput,
    EnvironmentDetails,
)
from temporal.workflows import DeployGitServiceWorkflow, ArchiveEnvWorkflow
from ..dtos import GitCommitInfo
from ..constants import GITLAB_NULL_COMMIT


class CreateGitlabAppAPIView(APIView):
    @extend_schema(
        request=CreateGitlabAppRequestSerializer,
        responses={200: CreateGitlabAppResponseSerializer},
        operation_id="createGitlabApp",
        summary="create a gitlab app",
    )
    def post(self, request: Request):
        form = CreateGitlabAppRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        url = urlparse(data["gitlab_url"])

        cache_id = f"{GitlabApp.SETUP_STATE_CACHE_PREFIX}:{generate_random_chars(32)}"
        cache_data = dict(data)
        cache_data["gitlab_url"] = f"{url.scheme}://{url.netloc}"
        cache.set(
            cache_id,
            cache_data,
            timeout=int(timedelta(minutes=10).total_seconds()),
        )

        serializer = CreateGitlabAppResponseSerializer(dict(state=cache_id))
        return Response(data=serializer.data)


class SetupGitlabAppAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        parameters=[SetupGitlabAppQuerySerializer],
        responses={303: None},
        operation_id="setupGitlabApp",
        summary="Set a gitlab app",
    )
    def get(self, request: Request):
        form = SetupGitlabAppQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        code = data["code"]
        state = data["state"]

        state_data: dict[str, str] = cache.get(state)

        # delete for preventing bad reuse
        cache.delete(state)
        match state:
            case state if isinstance(state, str) and state.startswith(
                GitlabApp.SETUP_STATE_CACHE_PREFIX
            ):
                response = requests.post(
                    f"{state_data['gitlab_url']}/oauth/token",
                    data=dict(
                        client_id=state_data["app_id"],
                        client_secret=state_data["app_secret"],
                        code=code,
                        grant_type="authorization_code",
                        redirect_uri=state_data["redirect_uri"],
                    ),
                )

                if not status.is_success(response.status_code):
                    raise BadRequest("invalid Gitlab app configuration")

                gitlab_token_data = response.json()

                gl_app = GitlabApp.objects.create(
                    gitlab_url=state_data["gitlab_url"],
                    name=state_data["name"],
                    app_id=state_data["app_id"],
                    secret=state_data["app_secret"],
                    redirect_uri=state_data["redirect_uri"],
                    refresh_token=gitlab_token_data["refresh_token"],
                )
                gl_app.fetch_all_repositories_from_gitlab()
                GitApp.objects.create(gitlab=gl_app)
            case state if isinstance(state, str) and state.startswith(
                GitlabApp.UPDATE_STATE_CACHE_PREFIX
            ):
                try:
                    git_app = (
                        GitApp.objects.filter(gitlab__app_id=state_data["app_id"])
                        .select_related("gitlab")
                        .get()
                    )
                except GitApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "The referenced gitlab app does not exists anymore"
                    )

                gl_app = cast(GitlabApp, git_app.gitlab)
                response = requests.post(
                    f"{gl_app.gitlab_url}/oauth/token",
                    data=dict(
                        client_id=gl_app.app_id,
                        client_secret=state_data["app_secret"],
                        code=code,
                        grant_type="authorization_code",
                        redirect_uri=state_data["redirect_uri"],
                    ),
                )

                if not status.is_success(response.status_code):
                    raise BadRequest("invalid Gitlab app configuration")

                gitlab_token_data = response.json()
                gl_app.refresh_token = gitlab_token_data["refresh_token"]
                gl_app.secret = state_data["app_secret"]
                gl_app.redirect_uri = state_data["redirect_uri"]
                gl_app.save()

                gl_app.fetch_all_repositories_from_gitlab()
            case _:
                raise BadRequest("Invalid state token")

        base_url = ""
        if settings.ENVIRONMENT != settings.PRODUCTION_ENV:
            base_url = "http://localhost:5173"

        return Response(
            headers={"Location": f"{base_url}/settings/git-apps"},
            status=status.HTTP_303_SEE_OTHER,
        )


class TestGitlabAppAPIView(APIView):
    @extend_schema(
        responses={
            200: inline_serializer(
                "TestGitlabAppResponseSerializer",
                fields={"repositories_count": serializers.IntegerField()},
            ),
        },
        operation_id="testGitlabApp",
    )
    def get(self, request: Request, id: str):
        try:
            git_app = (
                GitApp.objects.filter(gitlab__id=id).select_related("gitlab").get()
            )
        except GitApp.DoesNotExist:
            raise exceptions.NotFound(f"Gitlab app with id {id} does not exist")

        gl_app = cast(GitlabApp, git_app.gitlab)
        access_token = GitlabApp.ensure_fresh_access_token(gl_app)
        url = f"{gl_app.gitlab_url}/api/v4/projects"
        params = {
            "membership": "true",
        }
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        response = requests.get(
            url + "?" + urlencode(params, doseq=True), headers=headers
        )
        if not status.is_success(response.status_code):
            raise BadRequest(
                "This gitlab app may not be correctly installed or it has been deleted on gitlab"
            )

        return Response(
            data={
                # `x-total`` will not show if there is more than 10000+ repos,
                #  so we send just 10 001 to signal it
                "repositories_count": int(response.headers.get("x-total", 10_001)),
            }
        )


class SyncRepositoriesAPIView(APIView):

    @transaction.atomic()
    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                "SyncGitlabRepositoriesResponseSerializer",
                fields={"repositories_count": serializers.IntegerField()},
            ),
        },
        operation_id="syncGitlabRepos",
        summary="Sync GitLab repositories for a GitLab application",
    )
    def put(self, request: Request, id: str):
        try:
            gitapp = GitApp.objects.filter(gitlab__id=id).select_related("gitlab").get()
        except GitApp.DoesNotExist:
            raise exceptions.NotFound(
                "The referenced gitlab app does not exists on ZaneOps"
            )

        gitlab = cast(GitlabApp, gitapp.gitlab)
        gitlab.fetch_all_repositories_from_gitlab()
        return Response(
            data={
                "repositories_count": gitlab.repositories.count(),
            }
        )


class GitlabAppDetailsAPIView(RetrieveAPIView):
    serializer_class = GitlabAppSerializer
    lookup_field = "id"
    queryset = GitlabApp.objects.all()


class GitlabAppUpdateAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        request=GitlabAppUpdateRequestSerializer,
        responses={200: GitlabAppUpdateResponseSerializer},
    )
    def put(self, request: Request, id: str):
        try:
            git_app = (
                GitApp.objects.filter(gitlab__id=id).select_related("gitlab").get()
            )
        except GitApp.DoesNotExist:
            raise exceptions.NotFound(f"Gitlab app with id {id} does not exist")

        form = GitlabAppUpdateRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        gl_app = cast(GitlabApp, git_app.gitlab)
        gl_app.name = data["name"]
        gl_app.save()

        cache_id = f"{GitlabApp.UPDATE_STATE_CACHE_PREFIX}:{generate_random_chars(32)}"
        cache_data = dict(
            app_id=gl_app.app_id,
            app_secret=data["app_secret"],
            redirect_uri=data["redirect_uri"],
        )
        cache.set(
            cache_id,
            cache_data,
            timeout=int(timedelta(minutes=10).total_seconds()),
        )

        serializer = GitlabAppUpdateResponseSerializer(dict(state=cache_id))
        return Response(data=serializer.data)


@extend_schema(exclude=True)
class GitlabWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gitapp_webhook"

    @transaction.atomic()
    def post(self, request: Request):
        form = GitlabWebhookEventSerializer(
            data={
                "event": request.headers.get("x-gitlab-event"),
                "webhook_secret": request.headers.get("x-gitlab-token"),
            }
        )
        form.is_valid(raise_exception=True)

        event = cast(ReturnDict, form.data)["event"]
        webhook_secret = cast(ReturnDict, form.data)["webhook_secret"]

        event_serializer_map = {
            GitlabWebhookEvent.PUSH: GitlabWebhookPushEventRequestSerializer,
            GitlabWebhookEvent.MERGE_REQUEST: GitlabWebhookMergeRequestEventRequestSerializer,
        }

        serializer_class = event_serializer_map[event]
        body = request.data

        form = serializer_class(data=body)
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        try:
            gitapp = (
                GitApp.objects.filter(gitlab__webhook_secret=webhook_secret)
                .select_related("gitlab")
                .get()
            )
        except GitApp.DoesNotExist:
            raise exceptions.NotFound("Invalid webhook secret")

        gitlab = cast(GitlabApp, gitapp.gitlab)

        match form:
            case GitlabWebhookPushEventRequestSerializer():
                head_commit = data["commits"][-1] if len(data["commits"]) > 0 else None
                ref: str = data["ref"]
                is_branch_deleted = (
                    data["checkout_sha"] is None and data["after"] == GITLAB_NULL_COMMIT
                )

                # We only consider pushes to a branch
                # we ignore tags and other push events
                if ref.startswith("refs/heads/"):
                    head_branch_name = ref.replace("refs/heads/", "")
                    repository_url = data["repository"]["git_http_url"]

                    if is_branch_deleted:
                        environment_delete_payload: list[
                            tuple[EnvironmentDetails, str]
                        ] = []
                        matching_preview_envs = Environment.objects.filter(
                            is_preview=True,
                            preview_metadata__source_trigger=Environment.PreviewSourceTrigger.API,
                            preview_metadata__head_repository_url=repository_url,
                            preview_metadata__git_app=gitapp,
                            preview_metadata__branch_name=head_branch_name,
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
                                branch_name=head_branch_name,
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

            case GitlabWebhookMergeRequestEventRequestSerializer():
                merge_request = data["object_attributes"]
                base_repository_url = merge_request["target"]["git_http_url"]
                head_repository_url = merge_request["source"]["git_http_url"]
                head_branch_name = merge_request["source_branch"]
                base_branch_name = merge_request["target_branch"]

                is_fork = base_repository_url != head_repository_url

                workflows_to_run: List[StartWorkflowArg] = []
                workflows_signals: List[SignalWorkflowArg] = []

                match merge_request["action"]:
                    case "open":
                        affected_services = (
                            Service.get_services_triggered_by_pull_request_event(
                                gitapp=gitapp,
                                repository_url=base_repository_url,
                            )
                        )

                        for current_service in affected_services:
                            existing_preview_envs_count = (
                                Environment.objects.filter(
                                    is_preview=True,
                                    preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                                    preview_metadata__head_repository_url=head_repository_url,
                                    preview_metadata__service=current_service,
                                    preview_metadata__git_app=gitapp,
                                    preview_metadata__pr_number=merge_request["iid"],
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
                            env_name = f"preview-mr-{merge_request['iid']}-{current_service.slug}-{fake.slug()}".lower()
                            preview_meta = PreviewEnvMetadata.objects.create(
                                branch_name=head_branch_name,
                                source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                                service=current_service,
                                template=preview_template,
                                auto_teardown=preview_template.auto_teardown,
                                external_url=merge_request["url"],
                                git_app=gitapp,
                                head_repository_url=head_repository_url,
                                ttl_seconds=preview_template.ttl_seconds,
                                auth_enabled=preview_template.auth_enabled,
                                auth_user=preview_template.auth_user,
                                pr_author=data["user"]["username"],
                                pr_base_repo_url=base_repository_url,
                                pr_base_branch_name=base_branch_name,
                                auth_password=preview_template.auth_password,
                                deploy_state=(
                                    PreviewEnvMetadata.PreviewDeployState.PENDING
                                    if is_fork
                                    else PreviewEnvMetadata.PreviewDeployState.APPROVED
                                ),
                                pr_number=merge_request["iid"],
                                pr_title=merge_request["title"],
                            )

                            base_environment = cast(
                                Environment, preview_template.base_environment
                            )

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
                                project_id = data["project"]["id"]
                                issue_number = merge_request[
                                    "iid"
                                ]  # issue or PR number

                                # create issue comment

                                url = f"{gitlab.gitlab_url}/api/v4/projects/{project_id}/merge_requests/{issue_number}/notes"

                                # 2️⃣ Prepare the request
                                headers = {
                                    "Authorization": f"Bearer {GitlabApp.ensure_fresh_access_token(gitlab)}",
                                    "Accept": "application/vnd.github+json",
                                }
                                payload = {
                                    "body": preview_meta.get_pull_request_deployment_blocked_comment_body(
                                        cloned_service
                                    )
                                }

                                # 3️⃣ Make the POST request
                                response = requests.post(
                                    url, headers=headers, json=payload
                                )
                                # 4️⃣ Check the response
                                if response.status_code == status.HTTP_201_CREATED:
                                    data = response.json()
                                    print(
                                        "Comment created:",
                                        url + f"/{data['id']}",
                                    )
                                    print("Comment Body:\n", data["body"])

                                    # Update Preview metadata with the comment ID
                                    preview_meta.pr_comment_id = data["id"]
                                    preview_meta.save()
                                else:
                                    print(
                                        f"Error when trying to create a PR comment for the {preview_meta.service=} on the PR #{merge_request['iid']}({merge_request['url']}): ",
                                        response.status_code,
                                        response.text,
                                    )
                                pass

                            else:
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
                                    if (
                                        service.type
                                        == Service.ServiceType.DOCKER_REGISTRY
                                    ):
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

                                    if current_service.slug == service.slug:
                                        # 1️⃣ Define the API endpoint for creating a comment
                                        project_id = data["project"]["id"]
                                        issue_number = merge_request[
                                            "iid"
                                        ]  # issue or PR number

                                        # create issue comment

                                        url = f"{gitlab.gitlab_url}/api/v4/projects/{project_id}/merge_requests/{issue_number}/notes"

                                        # 2️⃣ Prepare the request
                                        headers = {
                                            "Authorization": f"Bearer {GitlabApp.ensure_fresh_access_token(gitlab)}",
                                            "Accept": "application/vnd.github+json",
                                        }
                                        payload = {
                                            "body": new_deployment.get_pull_request_deployment_comment_body()
                                        }

                                        # 3️⃣ Make the POST request
                                        response = requests.post(
                                            url, headers=headers, json=payload
                                        )
                                        # 4️⃣ Check the response
                                        if (
                                            response.status_code
                                            == status.HTTP_201_CREATED
                                        ):
                                            data = response.json()
                                            print(
                                                "Comment created:",
                                                url + f"/{data['id']}",
                                            )
                                            print("Comment Body:\n", data["body"])

                                            # Update Preview metadata with the comment ID
                                            preview_meta.pr_comment_id = data["id"]
                                            preview_meta.save()
                                        else:
                                            print(
                                                f"Error when trying to create a MR comment for the {service=} on the MR #{issue_number}({merge_request['url']}): ",
                                                response.status_code,
                                                response.text,
                                            )
                                        pass

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
                    case "update" if merge_request["state"] == "opened":
                        matching_preview_envs = Environment.objects.filter(
                            is_preview=True,
                            preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                            preview_metadata__head_repository_url=head_repository_url,
                            preview_metadata__git_app=gitapp,
                            preview_metadata__branch_name=head_branch_name,
                            preview_metadata__auto_teardown=True,
                            preview_metadata__pr_number=merge_request["iid"],
                        ).select_related("project", "preview_metadata")

                        for environment in matching_preview_envs:
                            preview_metadata = cast(
                                PreviewEnvMetadata, environment.preview_metadata
                            )
                            preview_metadata.pr_title = merge_request["title"]
                            preview_metadata.pr_base_branch_name = base_branch_name
                            preview_metadata.save()

                        # if there was a push on the branch of the merge request
                        is_push_action = merge_request.get("oldrev") is not None
                        if is_push_action:
                            affected_services = Service.get_services_triggered_by_pull_request_sync_event(
                                gitapp=gitapp,
                                repository_url=head_repository_url,
                                pr_number=merge_request["iid"],
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
                    case "close":
                        matching_preview_envs = Environment.objects.filter(
                            is_preview=True,
                            preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                            preview_metadata__head_repository_url=head_repository_url,
                            preview_metadata__git_app=gitapp,
                            preview_metadata__branch_name=head_branch_name,
                            preview_metadata__auto_teardown=True,
                            preview_metadata__pr_number=merge_request["iid"],
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
                        pass
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
