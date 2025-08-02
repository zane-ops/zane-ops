from typing import cast
import requests
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView, ListAPIView
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from ..serializers import (
    GitRepositoryListFilterSet,
    GithubWebhookEventSerializer,
    SetupGithubAppQuerySerializer,
    GithubAppSerializer,
    GithubWebhookPingRequestSerializer,
    GithubWebhookInstallationRequestSerializer,
    GithubWebhookEvent,
    GithubWebhookInstallationRepositoriesRequestSerializer,
    GitRepositorySerializer,
    GithubWebhookPushRequestSerializer,
)
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema, inline_serializer

from zane_api.views import BadRequest
from django.conf import settings

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status, serializers
from zane_api.models import GitApp, Service
from ..models import GitHubApp, GitRepository
from django_filters.rest_framework import DjangoFilterBackend
from zane_api.models import Deployment
from temporal.shared import DeploymentDetails
from temporal.client import TemporalClient
from temporal.workflows import DeployGitServiceWorkflow, CancelDeploymentSignalInput
from ..dtos import GitCommitInfo


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


class ListGithubRepositoriesAPIView(ListAPIView):
    serializer_class = GitRepositorySerializer
    queryset = (
        GitRepository.objects.filter()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = GitRepositoryListFilterSet

    def get_queryset(self) -> QuerySet[GitRepository]:  # type: ignore
        app_id = self.kwargs["id"]
        try:
            gh_app = GitHubApp.objects.get(id=app_id)
        except GitHubApp.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A GitHub app with the `{app_id}` does not exist."
            )

        return gh_app.repositories

    def filter_queryset(self, queryset: QuerySet[GitRepository]):
        queryset = super().filter_queryset(queryset)
        return queryset[:30]


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
                # We only consider pushes to a branch
                # we ignore tags and other push events
                if ref.startswith("refs/heads/"):
                    branch_name = ref.replace("refs/heads/", "")

                    repository_url = (
                        f"https://github.com/{data["repository"]["full_name"]}.git"
                    )

                    affected_services = Service.get_services_triggered_by_push_event(
                        gitapp=gitapp,
                        branch_name=branch_name,
                        repository_url=repository_url,
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
                            DeploymentDetails.from_deployment(deployment=new_deployment)
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

            case _:
                raise BadRequest("bad request")

        return Response(data={"success": True})
