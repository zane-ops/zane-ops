from typing import cast
from urllib.parse import urlencode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, exceptions
from drf_spectacular.utils import extend_schema
from temporal.workflows import AutoUpdateDockerServiceWorkflow
from temporal.client import TemporalClient
from temporal.constants import ZANEOPS_ONGOING_UPDATE_CACHE_KEY
from rest_framework.request import Request
from django.db import transaction
import requests
from rest_framework.utils.serializer_helpers import ReturnDict
from .serializers import (
    AutoUpdateRequestSerializer,
    AutoUpdateResponseSerializer,
    OngoingUpdateResponseSerializer,
)
from ..serializers import ErrorResponse409Serializer
from django.core.cache import cache
from .base import ResourceConflict


def check_image_exists(desired_image: str) -> bool:
    params = urlencode(query={"tag": desired_image}, doseq=True)
    response = requests.get(f"https://cdn.zaneops.dev/api/single-release?{params}")
    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        return desired_image == data.get("tag")
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return False


class TriggerUpdateView(APIView):
    """
    API endpoint to trigger the update workflow of ZaneOps
    """

    @extend_schema(
        request=AutoUpdateRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            200: AutoUpdateResponseSerializer,
        },
        summary="Trigger Auto-Update",
        description="Triggers the Docker auto-update workflow using Temporal.",
    )
    @transaction.atomic()
    def post(self, request: Request) -> Response:
        serializer = AutoUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ongoing_status = cache.get(ZANEOPS_ONGOING_UPDATE_CACHE_KEY, False)
        if ongoing_status:
            raise ResourceConflict(
                "ZaneOps is currently running an update in the background"
            )

        desired_version = cast(ReturnDict, serializer.validated_data)["desired_version"]

        if check_image_exists(desired_version):

            def on_commit():
                TemporalClient.start_workflow(
                    AutoUpdateDockerServiceWorkflow.run,
                    desired_version,
                    id=f"auto-update-{desired_version}",
                )

            transaction.on_commit(on_commit)

            response_serializer = AutoUpdateResponseSerializer(
                {"message": f"Auto-update workflow for  '{desired_version}' started."}
            )
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        else:
            raise exceptions.NotFound(
                f"The provided version `{desired_version}` is not a valid ZaneOps version"
            )


class CheckOngoingUpdateView(APIView):
    """
    API endpoint to check if the update workflow of ZaneOps is running
    """

    serializer_class = OngoingUpdateResponseSerializer

    @extend_schema(
        summary="Check ongoing update status of ZaneOps",
        description="Check if the auto-update workflow of ZaneOps is running.",
    )
    def get(self, request: Request):
        ongoing_status = cache.get(ZANEOPS_ONGOING_UPDATE_CACHE_KEY, False)
        response_serializer = OngoingUpdateResponseSerializer(
            {"update_ongoing": ongoing_status}
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
