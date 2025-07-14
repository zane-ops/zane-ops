from datetime import timedelta
from typing import cast
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
)
from drf_spectacular.utils import extend_schema, inline_serializer

# from zane_api.utils import jprint
from zane_api.views import BadRequest
from django.conf import settings

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status, serializers
from zane_api.models import GitApp
from ..models import GitlabApp
from django.core.cache import cache
from zane_api.utils import generate_random_chars
from rest_framework import permissions
from rest_framework.throttling import ScopedRateThrottle


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


class GitlabWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gitapp_webhook"

    @transaction.atomic()
    def post(self, request: Request):
        return Response(data={}, status=status.HTTP_501_NOT_IMPLEMENTED)
