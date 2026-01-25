import json
from urllib.parse import urlparse

from drf_spectacular.utils import extend_schema
from rest_framework import status, exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .base import InternalZaneAppPermission
from ..utils import Colors, escape_ansi
from datetime import datetime

from .helpers import ZaneServices
from .serializers import (
    DockerContainerLogsResponseSerializer,
    DockerContainerLogsRequestSerializer,
    HTTPServiceLogSerializer,
)
from search.dtos import RuntimeLogDto, RuntimeLogLevel, RuntimeLogSource
from search.loki_client import LokiSearchClient
from django.conf import settings
from django.utils import timezone
from typing import cast

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListAPIView, RetrieveAPIView


from search.serializers import RuntimeLogsSearchSerializer

from .base import EMPTY_CURSOR_RESPONSE

from .serializers import (
    DeploymentBuildLogsQuerySerializer,
    DeploymentRuntimeLogsQuerySerializer,
    HttpLogFieldsQuerySerializer,
    HttpLogFieldsResponseSerializer,
    DeploymentHttpLogsPagination,
    DeploymentHttpLogsFilterSet,
)

from ..models import (
    Project,
    Service,
    Deployment,
    HttpLog,
    Environment,
)
from ..serializers import HttpLogSerializer

from rest_framework.utils.serializer_helpers import ReturnDict
from temporal.helpers import ZaneProxyClient
from django.db.models import Q


def _build_http_log(log_time: str, log_content: dict, **extra_fields) -> HttpLog:
    """Build an HttpLog from proxy log content with common fields extracted."""
    req = log_content["request"]
    duration_in_seconds = log_content["duration"]
    full_url = urlparse(f"https://{req['host']}{req['uri']}")

    client_ip = req["headers"].get("X-Forwarded-For", req["remote_ip"])
    user_agent = req["headers"].get("User-Agent")

    return HttpLog(
        time=log_time,
        request_duration_ns=int(duration_in_seconds * 1_000_000_000),
        request_path=full_url.path,
        request_query=full_url.query,
        request_protocol=req["proto"],
        request_host=req["host"],
        status=log_content["status"],
        request_headers=req["headers"],
        response_headers=log_content["resp_headers"],
        request_user_agent=user_agent[0] if isinstance(user_agent, list) else None,
        request_ip=client_ip[0].split(",")[0]
        if isinstance(client_ip, list)
        else client_ip,
        request_uuid=log_content.get("uuid"),
        request_method=req["method"],
        **extra_fields,
    )


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
                                stack_id = content.get("zane_stack_id")
                                registry_id = content.get("zane_registry_id")
                                if service_id or stack_id or registry_id:
                                    log_serializer = HTTPServiceLogSerializer(
                                        data=content
                                    )
                                    if log_serializer.is_valid():
                                        log_content: dict = log_serializer.data  # type: ignore

                                        service_type = log_content.get(
                                            "zane_service_type"
                                        )
                                        match service_type:
                                            case ZaneProxyClient.ServiceType.BUILD_REGISTRY:
                                                if registry_id:
                                                    http_logs.append(
                                                        _build_http_log(
                                                            log["time"],
                                                            log_content,
                                                            registry_id=registry_id,
                                                        )
                                                    )
                                            case ZaneProxyClient.ServiceType.COMPOSE_STACK_SERVICE:
                                                stack_service_name = content.get(
                                                    "zane_stack_service_name"
                                                )
                                                if stack_service_name:
                                                    http_logs.append(
                                                        _build_http_log(
                                                            log["time"],
                                                            log_content,
                                                            stack_id=stack_id,
                                                            stack_service_name=stack_service_name,
                                                        )
                                                    )
                                            case ZaneProxyClient.ServiceType.MANAGED_SERVICE:
                                                upstream: str = log_content.get(
                                                    "zane_deployment_upstream"
                                                )  # type: ignore
                                                deployment_id = content.get(
                                                    "zane_deployment_id"
                                                )
                                                # For backward compatibility
                                                if deployment_id is not None:
                                                    if (
                                                        "blue.zaneops.internal"
                                                        in upstream
                                                    ):
                                                        deployment_id = log_content.get(
                                                            "zane_deployment_blue_hash"
                                                        )
                                                    elif (
                                                        "green.zaneops.internal"
                                                        in upstream
                                                    ):
                                                        deployment_id = log_content.get(
                                                            "zane_deployment_green_hash"
                                                        )

                                                if deployment_id:
                                                    http_logs.append(
                                                        _build_http_log(
                                                            log["time"],
                                                            log_content,
                                                            service_id=log_content.get(
                                                                "zane_service_id"
                                                            ),
                                                            deployment_id=deployment_id,
                                                        )
                                                    )

                                        continue
                        case ZaneServices.API | ZaneServices.WORKER:
                            # do nothing for now...
                            pass
                        case _:
                            deployment_id = json_tag["deployment_id"]
                            simple_logs.append(
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
                                    content=log["log"],
                                    content_text=escape_ansi(log["log"]),
                                )
                            )

            start_time = datetime.now()
            search_client = LokiSearchClient(host=settings.LOKI_HOST)
            search_client.bulk_insert(simple_logs)
            HttpLog.objects.bulk_create(http_logs)
            end_time = datetime.now()

            response = DockerContainerLogsResponseSerializer(
                {
                    "simple_logs_inserted": len(simple_logs),
                    "http_logs_inserted": len(http_logs),
                }
            )
            print("====== LOGS INGEST ======")
            print(
                f"Took {(end_time - start_time).microseconds / 1000}{Colors.GREY}ms{Colors.ENDC}"
            )
            print(
                f"Simple logs inserted = {Colors.BLUE}{len(simple_logs)}{Colors.ENDC}"
            )
            print(f"HTTP logs inserted = {Colors.BLUE}{len(http_logs)}{Colors.ENDC}")
            return Response(response.data, status=status.HTTP_200_OK)


class HttpLogsFieldsAPIView(APIView):
    serializer_class = HttpLogFieldsResponseSerializer

    @extend_schema(
        summary="Get http logs fields values",
        parameters=[HttpLogFieldsQuerySerializer],
    )
    def get(self, request: Request):
        form = HttpLogFieldsQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.data)
        field = data["field"]
        value = data["value"]

        service_id = data.get("service_id")
        stack_id = data.get("stack_id")
        deployment_id = data.get("deployment_hash")

        condition = Q()
        if len(value) > 0:
            condition &= Q(**{f"{field}__startswith": value})

        if service_id:
            condition &= Q(service_id=service_id)

        if stack_id:
            condition &= Q(stack_id=stack_id)

        if deployment_id:
            condition &= Q(deployment_id=deployment_id)

        values = (
            HttpLog.objects.filter(condition)
            .order_by(field)
            .values_list(field, flat=True)
            .distinct()[:7]
        )

        seriaziler = HttpLogFieldsResponseSerializer([item for item in values])
        return Response(seriaziler.data)


class HttpLogsAPIView(ListAPIView):
    serializer_class = HttpLogSerializer
    queryset = HttpLog.objects.all()  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = DeploymentHttpLogsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeploymentHttpLogsFilterSet

    @extend_schema(
        summary="Get HTTP logs",
    )
    def get(self, request: Request, *args, **kwargs):
        try:
            print("====== HTTP LOGS SEARCH ======")
            print(f"Params: {Colors.GREY}{request.query_params}{Colors.ENDC}")
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid cursor" in str(e.detail):
                return Response(EMPTY_CURSOR_RESPONSE)
            raise e


@extend_schema(summary="Get single http log")
class SingleHttpLogAPIView(RetrieveAPIView):
    serializer_class = HttpLogSerializer
    queryset = HttpLog.objects.all()
    lookup_field = "request_uuid"


class ServiceDeploymentRuntimeLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer

    @extend_schema(
        summary="Get deployment logs", parameters=[DeploymentRuntimeLogsQuerySerializer]
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)

            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = Service.objects.get(
                slug=service_slug, project=project, environment=environment
            )
            deployment = Deployment.objects.get(service=service, hash=deployment_hash)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )
        else:
            form = DeploymentRuntimeLogsQuerySerializer(data=request.query_params)
            print(f"{request.query_params=}")
            if form.is_valid(raise_exception=True):
                search_client = LokiSearchClient(host=settings.LOKI_HOST)
                data = search_client.search(
                    query=dict(**form.validated_data, deployment_id=deployment.hash),  # type: ignore
                )
                return Response(data)


class ServiceDeploymentBuildLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer

    @extend_schema(
        summary="Get deployment build logs",
        parameters=[DeploymentBuildLogsQuerySerializer],
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug)

            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = Service.objects.get(
                slug=service_slug, project=project, environment=environment
            )
            deployment = Deployment.objects.get(service=service, hash=deployment_hash)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )
        else:
            form = DeploymentBuildLogsQuerySerializer(data=request.query_params)
            print(f"{request.query_params=}")
            if form.is_valid(raise_exception=True):
                search_client = LokiSearchClient(host=settings.LOKI_HOST)
                data = search_client.search(
                    query=dict(
                        cursor=cast(ReturnDict, form.validated_data).get("cursor"),
                        deployment_id=deployment.hash,
                        source=[RuntimeLogSource.BUILD, RuntimeLogSource.SYSTEM],
                    ),  # type: ignore
                )
                return Response(data)
