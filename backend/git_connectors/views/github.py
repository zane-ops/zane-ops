from typing import cast
import requests
from rest_framework.views import APIView
from rest_framework import exceptions
from ..serializers import SetupGithubAppQuerySerializer
from drf_spectacular.utils import extend_schema
from zane_api.utils import jprint
from zane_api.views import BadRequest
from django.conf import settings

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status
from zane_api.models import GitApp, GithubApp


class SetupCreateGithubConnectorAPIView(APIView):

    @transaction.atomic()
    @extend_schema(
        responses={status.HTTP_303_SEE_OTHER: None},
        summary="setup github connector",
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
                        f"Git app with id {app_id} does not exist"
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
