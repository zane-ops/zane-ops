from typing import cast
import requests
from rest_framework.views import APIView
from rest_framework import exceptions
from .serializers import (
    GitAppSerializer,
    SetupGithubAppQuerySerializer,
)
from drf_spectacular.utils import extend_schema

# from rest_framework.response import Response
# from zane_api.views import (
#     ErrorResponse409Serializer,
#     ResourceConflict,
# )
# from django.db import transaction, IntegrityError
from rest_framework.request import Request
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status
from zane_api.models import GitApp, GithubApp


class SetupCreateGithubConnectorAPIView(APIView):
    serializer = GitAppSerializer

    @extend_schema(
        summary="setup github connector",
        parameters=[SetupGithubAppQuerySerializer],
    )
    def get(self, request: Request):
        form = SetupGithubAppQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        code = data["code"]
        if data["state"] == "create":
            url = f"https://api.github.com/app-manifests/{code}/conversions"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            response = requests.post(url, headers=headers)

            if not status.is_success(response.status_code):
                raise exceptions.PermissionDenied(
                    "invalid Github app installation code"
                )

            github_manifest_data = response.json()

            github_app = GithubApp.objects.get_or_create(
                app_url=github_manifest_data["html_url"]
            )
            git_app = GitApp.objects.get_or_create(github=github_app)
