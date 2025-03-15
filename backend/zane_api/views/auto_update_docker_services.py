from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from django.conf import settings
from temporalio.client import Client
from drf_spectacular.utils import extend_schema
from ..temporal.workflows import AutoUpdateDockerServiceWorkflow

from .serializers import (
    AutoUpdateRequestSerializer,
    AutoUpdateResponseSerializer,
)


class TriggerAutoUpdateView(APIView):
    """
    API endpoint to trigger the Docker auto-update workflow.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "auto_update"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        request=AutoUpdateRequestSerializer,
        responses={202: AutoUpdateResponseSerializer},
        summary="Trigger Auto-Update",
        description="Triggers the Docker auto-update workflow using Temporal.",
    )
    def post(self, request) -> Response:
        serializer = AutoUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        desired_image = serializer.validated_data["desired_image"]

        try:

            client = Client.connect(settings.TEMPORALIO_SERVER_URL)

            client.start_workflow(
                AutoUpdateDockerServiceWorkflow.run,
                desired_image,
                id=f"auto-update-{desired_image}",
                task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
            )

            response_serializer = AutoUpdateResponseSerializer(
                {
                    "message": f"Auto-update workflow for image '{desired_image}' started."
                }
            )
            return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            raise exceptions.APIException(f"Failed to trigger auto-update: {e}")
