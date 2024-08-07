from adrf.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, serializers
from rest_framework.request import Request
from rest_framework.response import Response

from ..shared import DeployPayload
from ..temporal import start_workflow
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
            payload = DeployPayload(slug=data["slug"])
            handle = await start_workflow(
                GetProjectWorkflow.run,
                payload,
                id=f"deploy-{payload.slug}",
            )
            return Response(data={"workflow_id": handle.id}, status=status.HTTP_200_OK)
