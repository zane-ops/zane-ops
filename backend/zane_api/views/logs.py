import json
from urllib.parse import urlparse

from drf_spectacular.utils import extend_schema
import requests
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .base import InternalZaneAppPermission
from ..utils import Colors
from ..dtos import RuntimeLogLevel, RuntimeLogSource
import traceback


from .helpers import ZaneServices
from .serializers import (
    DockerContainerLogsResponseSerializer,
    DockerContainerLogsRequestSerializer,
    HTTPServiceLogSerializer,
)
from ..models import (
    SimpleLog,
    HttpLog,
)
from uuid import uuid4
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from datetime import timezone as tz


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

            simple_logs: list[dict] = []
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

                                            try:
                                                log["time"] = int(log["time"])
                                                log_time = datetime.fromtimestamp(
                                                    log["time"]
                                                    / 1e9,  # convert nanoseconds to seconds,
                                                    tz.utc,
                                                )
                                            except ValueError:
                                                # this log is probably formatted as an ISO string
                                                log_time = datetime.fromisoformat(
                                                    log["time"]
                                                )
                                            except Exception as e:
                                                print("Error parsing log time : ", e)
                                                traceback.print_exc()
                                                continue

                                            http_logs.append(
                                                HttpLog(
                                                    time=log_time,
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
                            simple_logs.append(
                                dict(
                                    id=str(uuid4()),
                                    source=RuntimeLogSource.SERVICE,
                                    level=(
                                        RuntimeLogLevel.INFO
                                        if log["source"] == "stdout"
                                        else RuntimeLogLevel.ERROR
                                    ),
                                    content=log["log"],
                                    time=log["time"],
                                    created_at=timezone.now().isoformat(),
                                    deployment_id=deployment_id,
                                    service_id=service_id,
                                    content_text=SimpleLog.escape_ansi(log["log"]),
                                )
                            )
            HttpLog.objects.bulk_create(http_logs)

            response = requests.post(
                f"{settings.QUICKWIT_API_URL}/api/v1/{settings.LOGS_INDEX_NAME}/ingest?commit=force",
                headers={"Content-Type": "application/json"},
                data="\n".join(json.dumps(log) for log in simple_logs),
            )
            response.raise_for_status()

            data = DockerContainerLogsResponseSerializer(
                {
                    "simple_logs_inserted": len(simple_logs),
                    "http_logs_inserted": len(http_logs),
                }
            ).data
            print("====== LOGS INGEST ======")
            print(
                f"Simple logs inserted = {Colors.BLUE}{len(simple_logs)}{Colors.ENDC}"
            )
            print(f"HTTP logs inserted = {Colors.BLUE}{len(http_logs)}{Colors.ENDC}")
            return Response(data, status=status.HTTP_200_OK)
