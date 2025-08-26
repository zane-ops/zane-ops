from typing import cast
from urllib.parse import urlencode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, exceptions
from drf_spectacular.utils import extend_schema
from temporal.workflows import AutoUpdateDockerServiceWorkflow
from temporal.client import TemporalClient
from rest_framework.request import Request
from django.db import transaction
import requests
from rest_framework.utils.serializer_helpers import ReturnDict
from .serializers import (
    AutoUpdateRequestSerializer,
    AutoUpdateResponseSerializer,
)


def check_image_exists(desired_image: str) -> bool:
    params = urlencode(query={"tag": desired_image}, doseq=True)
    response = requests.get(f"https://cdn.zaneops.dev/api/single-release?{params}")
    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        return desired_image == data.get("tag")
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return False


from ..permissions import SettingsPermission


class TriggerUpdateView(APIView):
    """
    API endpoint to trigger the update workflow of ZaneOps
    """

    serializer_class = AutoUpdateResponseSerializer
    permission_classes = [SettingsPermission]

    @extend_schema(
        request=AutoUpdateRequestSerializer,
        summary="Trigger Auto-Update",
        description="Triggers the Docker auto-update workflow using Temporal.",
    )
    @transaction.atomic()
    def post(self, request: Request) -> Response:
        serializer = AutoUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        desired_version = cast(ReturnDict, serializer.validated_data)["desired_version"]

        if check_image_exists(desired_version):

            transaction.on_commit(
                lambda: TemporalClient.start_workflow(
                    AutoUpdateDockerServiceWorkflow.run,
                    desired_version,
                    id=f"auto-update-{desired_version}",
                )
            )

            response_serializer = AutoUpdateResponseSerializer(
                {"message": f"Auto-update workflow for  '{desired_version}' started."}
            )
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        else:
            raise exceptions.NotFound(
                f"The provided version `{desired_version}` is not a valid ZaneOps version"
            )
