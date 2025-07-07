from datetime import timedelta
from typing import cast
from urllib.parse import urlencode, urlparse
import requests
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView, ListAPIView
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from ..serializers import (
    CreateGitlabAppRequestSerializer,
    CreateGitlabAppResponseSerializer,
    SetupGitlabAppQuerySerializer,
)
from django.db.models import QuerySet
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
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from zane_api.utils import generate_random_chars


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

        state = generate_random_chars(32)
        cache_data = dict(data)
        cache_data["gitlab_url"] = f"{url.scheme}://{url.netloc}"
        cache.set(
            f"gitlab-setup:{state}",
            cache_data,
            timeout=int(timedelta(minutes=10).total_seconds()),
        )

        serializer = CreateGitlabAppResponseSerializer(dict(state=state))
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

        state_data: dict[str, str] = cache.get(
            f"{GitlabApp.STATE_CACHE_PREFIX}:{state}"
        )
        # delete for preventing bad reuse
        cache.delete(f"{GitlabApp.STATE_CACHE_PREFIX}:{state}")

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
            name=state_data["name"],
            app_id=state_data["app_id"],
            secret=state_data["app_secret"],
            redirect_uri=state_data["redirect_uri"],
            refresh_token=gitlab_token_data["refresh_token"],
        )
        gl_app.fetch_all_repositories_from_gitlab()
        GitApp.objects.create(gitlab=gl_app)

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
        access_token = gl_app.ensure_fresh_access_token()
        url = f"{gl_app.gitlab_url}/api/v4/projects"
        params = {
            "membership": "true",
            "owned": "true",
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
