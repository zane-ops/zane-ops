from drf_spectacular.utils import extend_schema
from rest_framework import status, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import (
    DockerContainerLogsResponseSerializer,
    DockerContainerLogsRequestSerializer,
)


class LogTailAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "log_collect"
    throttle_classes = [ScopedRateThrottle]
    serializer_class = DockerContainerLogsResponseSerializer

    @extend_schema(
        request=DockerContainerLogsRequestSerializer,
        operation_id="collectContainerLogs",
    )
    def post(self, request: Request):
        serializer = DockerContainerLogsRequestSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            logs = serializer.data
            for log in logs:
                if log["service"] == "proxy":
                    print(f"{log=}")

        response = DockerContainerLogsResponseSerializer({"success": True})
        return Response(response.data, status=status.HTTP_200_OK)
