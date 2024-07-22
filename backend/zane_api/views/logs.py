import json

from drf_spectacular.utils import extend_schema
from rest_framework import status, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .helpers import ZaneServices
from .serializers import (
    DockerContainerLogsResponseSerializer,
    DockerContainerLogsRequestSerializer,
    HTTPServiceLogSerializer,
)
from ..models import SimpleLog, HttpLog


@extend_schema(exclude=True)
class LogTailAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "log_collect"
    throttle_classes = [ScopedRateThrottle]
    serializer_class = DockerContainerLogsResponseSerializer

    def post(self, request: Request):
        serializer = DockerContainerLogsRequestSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            logs = serializer.data

            simple_logs: list[SimpleLog] = []
            http_logs: list[HttpLog] = []

            for log in logs:
                try:
                    json_tag = json.loads(log["tag"])
                except json.JSONDecodeError:
                    # Ignore this log
                    continue
                else:
                    service_id = json_tag.get("service_id")
                    match service_id:
                        case None:
                            # Ignore this log
                            continue
                        case ZaneServices.PROXY:
                            try:
                                content = json.loads(log["log"])
                            except json.JSONDecodeError:
                                pass
                            else:
                                service_id = content.get("zane_service_id")
                                if service_id:
                                    log_serializer = HTTPServiceLogSerializer(
                                        data=content
                                    )
                                    if log_serializer.is_valid():
                                        log_content = log_serializer.data
                                        upstream: str = log_content.get(
                                            "zane_deployment_upstream"
                                        )
                                        deployment_id = None
                                        if "blue.zaneops.internal" in upstream:
                                            deployment_id = log_content.get(
                                                "zane_deployment_blue_hash"
                                            )
                                        elif "green.zaneops.internal" in upstream:
                                            deployment_id = log_content.get(
                                                "zane_deployment_green_hash"
                                            )

                                        if deployment_id is not None:
                                            req = log_content.get("request")
                                            duration_in_seconds = log_content.get(
                                                "duration"
                                            )
                                            http_logs.append(
                                                HttpLog(
                                                    time=log["time"],
                                                    service_id=log_content.get(
                                                        "zane_service_id"
                                                    ),
                                                    deployment_id=deployment_id,
                                                    request_duration_ns=(
                                                        duration_in_seconds
                                                        * 1_000_000_000
                                                    ),
                                                    request_uri=req["uri"],
                                                    request_host=req["host"],
                                                    status=log_content.get("status"),
                                                    request_headers=req.get("headers"),
                                                    response_headers=log_content.get(
                                                        "resp_headers"
                                                    ),
                                                    request_ip=req.get("remote_ip"),
                                                    request_method=req.get("method"),
                                                )
                                            )
                                            continue
                                simple_logs.append(
                                    SimpleLog(
                                        source=SimpleLog.LogSource.PROXY,
                                        level=(
                                            SimpleLog.LogLevel.INFO
                                            if log["source"] == "stdout"
                                            else SimpleLog.LogLevel.ERROR
                                        ),
                                        content=content,
                                        time=log["time"],
                                    )
                                )

                        case ZaneServices.API | ZaneServices.WORKER:
                            # do nothing for now...
                            pass
                        case _:
                            deployment_id = json_tag["deployment_id"]
                            simple_logs.append(
                                SimpleLog(
                                    source=SimpleLog.LogSource.SERVICE,
                                    level=(
                                        SimpleLog.LogLevel.INFO
                                        if log["source"] == "stdout"
                                        else SimpleLog.LogLevel.ERROR
                                    ),
                                    content=log["log"],
                                    time=log["time"],
                                    deployment_id=deployment_id,
                                    service_id=service_id,
                                )
                            )
            SimpleLog.objects.bulk_create(simple_logs)
            HttpLog.objects.bulk_create(http_logs)

            response = DockerContainerLogsResponseSerializer(
                {
                    "simple_logs_inserted": len(simple_logs),
                    "http_logs_inserted": len(http_logs),
                }
            )
            return Response(response.data, status=status.HTTP_200_OK)
