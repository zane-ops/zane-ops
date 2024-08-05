from adrf.views import APIView
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from ..shared import DeployPayload
from ..workflows import GetProjectWorkflow


class TestInput(serializers.Serializer):
    slug = serializers.CharField(required=True)


@extend_schema(exclude=True)
class TestWorkflowAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    async def post(self, request: Request):
        form = TestInput(data=request.data)

        if form.is_valid(raise_exception=True):
            data = form.data
            client = await Client.connect(
                settings.TEMPORALIO_SERVER_URL, namespace="default"
            )
            payload = DeployPayload(slug=data["slug"])
            try:
                handle = await client.start_workflow(
                    GetProjectWorkflow.run,
                    payload,
                    id=f"hello-{payload.slug}",
                    task_queue="main-task-queue",
                )
            except WorkflowAlreadyStartedError:
                pass
            return Response(data={"data": data}, status=status.HTTP_200_OK)
