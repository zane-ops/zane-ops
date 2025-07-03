from typing import cast
import requests
from rest_framework.views import APIView
from rest_framework.generics import UpdateAPIView
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from ..serializers import (
    GithubWebhookEventSerializer,
    SetupGithubAppQuerySerializer,
    GithubAppNameSerializer,
    GithubWebhookPingRequestSerializer,
    GithubWebhookInstallationRequestSerializer,
    GithubWebhookEvent,
)
from drf_spectacular.utils import extend_schema, inline_serializer
from zane_api.utils import jprint
from zane_api.views import BadRequest
from django.conf import settings

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status, serializers
from zane_api.models import GitApp
from ..models import GithubApp, GitRepository


class SetupCreateGithubAppAPIView(APIView):

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
                installation_id: str = data["installation_id"]

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

                gh_app: GithubApp = git_app.github  # type: ignore
                gh_app.installation_id = installation_id
                gh_app.save()

            case "create":
                url = f"https://api.github.com/app-manifests/{code}/conversions"
                headers = {
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                response = requests.post(url, headers=headers)

                jprint(response.json())

                if not status.is_success(response.status_code):
                    raise BadRequest("invalid Github app installation code")

                github_manifest_data = response.json()

                github_app = GithubApp.objects.filter(
                    app_id=github_manifest_data["id"]
                ).first()

                if github_app is None:
                    github_app = GithubApp.objects.create(
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
                raise exceptions.APIException("This code should be unreachable !")

        base_url = ""
        if settings.ENVIRONMENT != settings.PRODUCTION_ENV:
            base_url = "http://localhost:5173"

        return Response(
            headers={"Location": f"{base_url}/settings/git-connectors"},
            status=status.HTTP_303_SEE_OTHER,
        )


class RenameGithubAppAPIView(UpdateAPIView):
    serializer_class = GithubAppNameSerializer
    queryset = GithubApp.objects.all()
    lookup_field = "id"
    http_method_names = ["patch"]


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

        github_app: GithubApp = git_app.github  # type: ignore
        access_token = github_app.get_installation_token()
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
    throttle_scope = "github_webhook"

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
        }

        serializer_class = event_serializer_map[event]
        form = serializer_class(data=request_data)
        form.is_valid(raise_exception=True)
        data = form.data
        print(f"{request.headers=}")

        match form:
            case GithubWebhookPingRequestSerializer():
                try:
                    gh_app = GithubApp.objects.get(app_id=data["hook"]["app_id"])
                except GithubApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )

                verified = gh_app.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")
            case GithubWebhookInstallationRequestSerializer():
                try:
                    gh_app = GithubApp.objects.get(
                        app_id=data["installation"]["app_id"]
                    )
                except GithubApp.DoesNotExist:
                    raise exceptions.NotFound(
                        "This github app has not been registered in this ZaneOps instance"
                    )
                verified = gh_app.verify_signature(
                    payload_body=request_body,
                    signature_header=signature,
                )
                if not verified:
                    raise BadRequest("Invalid webhook signature")

                repositories = data["repositories"]

                def map_repository(repository: dict[str, str]):
                    owner, repo = repository["full_name"].split("/")
                    url = f"http://github.com/{owner}/{repo}"
                    return GitRepository(
                        owner=owner,
                        repo=repo,
                        url=url,
                        private=repository["private"],
                    )

                mapped = list(map(map_repository, repositories))
                existing_repos = GitRepository.objects.filter(
                    url__in=[repo.url for repo in mapped]
                ).values_list("url", flat=True)
                new_repos = [repo for repo in mapped if repo.url not in existing_repos]

                gh_app.repositories.add(*GitRepository.objects.bulk_create(new_repos))
            case _:
                raise BadRequest("bad request")

        return Response(data={"success": True})
