import json
from urllib.parse import urlparse

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .base import InternalZaneAppPermission
from ..utils import Colors, escape_ansi, truncate_utf8
from datetime import datetime

from .helpers import ZaneServices
from .serializers import (
    DockerContainerLogsResponseSerializer,
    DockerContainerLogsRequestSerializer,
    HTTPServiceLogSerializer,
)
from ..models import HttpLog
from search.dtos import RuntimeLogDto, RuntimeLogLevel, RuntimeLogSource
from search.client import SearchClient
from search.constants import ELASTICSEARCH_BYTE_LIMIT
from django.conf import settings
from django.utils import timezone


@extend_schema(exclude=True)
class LogIngestAPIView(APIView):
    permission_classes = [InternalZaneAppPermission]
    throttle_scope = "log_collect"
    throttle_classes = [ScopedRateThrottle]
    serializer_class = DockerContainerLogsResponseSerializer

    def post(self, request: Request):
        serializer = DockerContainerLogsRequestSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            logs = serializer.data

            simple_logs: list[RuntimeLogDto] = []
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

                                        if deployment_id:
                                            req = log_content.get("request")
                                            duration_in_seconds = log_content.get(
                                                "duration"
                                            )

                                            full_url = urlparse(
                                                f"https://{req['host']}{req['uri']}"
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
                                                    request_path=full_url.path,
                                                    request_query=full_url.query,
                                                    request_protocol=req["proto"],
                                                    request_host=req["host"],
                                                    status=log_content["status"],
                                                    request_headers=req["headers"],
                                                    response_headers=log_content[
                                                        "resp_headers"
                                                    ],
                                                    request_ip=req["remote_ip"],
                                                    request_id=log_content.get("uuid"),
                                                    request_method=req["method"],
                                                )
                                            )
                                            continue
                        case ZaneServices.API | ZaneServices.WORKER:
                            # do nothing for now...
                            pass
                        case _:
                            deployment_id = json_tag["deployment_id"]
                            simple_logs.extend(
                                RuntimeLogDto(
                                    time=log["time"],
                                    created_at=timezone.now(),
                                    level=(
                                        RuntimeLogLevel.INFO
                                        if log["source"] == "stdout"
                                        else RuntimeLogLevel.ERROR
                                    ),
                                    source=RuntimeLogSource.SERVICE,
                                    service_id=service_id,
                                    deployment_id=deployment_id,
                                    content=message,
                                    content_text=escape_ansi(message),
                                )
                                for message in truncate_utf8(
                                    log["log"], ELASTICSEARCH_BYTE_LIMIT
                                )
                            )

            start_time = datetime.now()
            search_client = SearchClient(host=settings.ELASTICSEARCH_HOST)
            search_client.bulk_insert(
                map(
                    lambda log: dict(
                        _index=settings.ELASTICSEARCH_LOGS_INDEX,
                        **log.to_es_dict(),
                    ),
                    simple_logs,
                )
            )

            HttpLog.objects.bulk_create(http_logs)
            end_time = datetime.now()

            response = DockerContainerLogsResponseSerializer(
                {
                    "simple_logs_inserted": len(simple_logs),
                    "http_logs_inserted": len(http_logs),
                }
            )
            print("====== LOGS INGEST ======")
            print(f"Took {end_time - start_time}")
            print(
                f"Simple logs inserted = {Colors.BLUE}{len(simple_logs)}{Colors.ENDC}"
            )
            print(f"HTTP logs inserted = {Colors.BLUE}{len(http_logs)}{Colors.ENDC}")
            return Response(response.data, status=status.HTTP_200_OK)
