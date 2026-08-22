import json
import math
from urllib.parse import urlparse

from drf_spectacular.utils import extend_schema
from rest_framework import status, exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.db.models import QuerySet

from ..permissions import (
    InternalZaneAppPermission,
    HasWorkspace,
    IsWorkspaceMember,
    get_accessible_projects,
)
import uuid
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
from typing import Literal, cast

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListAPIView, RetrieveAPIView


from search.serializers import (
    RuntimeLogsSearchSerializer,
    RuntimeLogsContextSerializer,
    RuntimeLogsContextParamsSerializer,
)

from .base import EMPTY_CURSOR_RESPONSE

from .serializers import (
    DeploymentBuildLogsQuerySerializer,
    DeploymentRuntimeLogsQuerySerializer,
    HttpLogFieldsQuerySerializer,
    HttpLogFieldsResponseSerializer,
    DeploymentHttpLogsPagination,
    DeploymentHttpLogsFilterSet,
    ProxyServiceLogSerializer,
)

from ..models import (
    Project,
    Service,
    Deployment,
    HttpLog,
    Environment,
)
from ..serializers import HttpLogSerializer
from compose.models import ComposeStack

from temporal.proxy import ZaneProxyClient

from django.db.models import Q
from zane_api.geoip import lookup_country_code


def _build_http_log(
    log_time: str, log_content: dict, source: str | None, **extra_fields
) -> HttpLog | None:
    """Build an HttpLog from proxy log content with common fields extracted."""
    req = log_content["request"]
    duration_in_seconds = log_content["duration"]
    full_url = urlparse(f"https://{req['host']}{req['uri']}")

    client_ip = req["headers"].get("X-Forwarded-For", req["remote_ip"])
    request_ip = (
        client_ip[0].split(",")[0] if isinstance(client_ip, list) else client_ip
    )

    user_agent = req["headers"].get("User-Agent")

    log_source = HttpLog.LogSource.UNKNOWN

    # Static files should be ignored
    is_zaneops_ignored_path = any(
        [
            full_url.path.startswith(path)
            for path in settings.ZANE_OPS_STATIC_PATH_PREFIXES
        ],
    )
    match source:
        case ZaneProxyClient.ServiceType.MANAGED_SERVICE:
            log_source = HttpLog.LogSource.SERVICE
        case ZaneProxyClient.ServiceType.COMPOSE_STACK_SERVICE:
            log_source = HttpLog.LogSource.COMPOSE_STACK
        case ZaneProxyClient.ServiceType.BUILD_REGISTRY:
            log_source = HttpLog.LogSource.BUILD_REGISTRY
        case ZaneProxyClient.ServiceType.ZANE_OPS:
            if is_zaneops_ignored_path:
                return
            log_source = (
                HttpLog.LogSource.ZANE_OPS_API
                if full_url.path.startswith("/api")
                else HttpLog.LogSource.ZANE_OPS_FRONTEND
            )
        case None:
            log_source = HttpLog.LogSource.UNKNOWN

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
        request_ip=request_ip,
        request_uuid=log_content.get("uuid", str(uuid.uuid4())),
        request_method=req["method"],
        source=log_source,
        request_country_code=lookup_country_code(request_ip),
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
                            pass
                        case ZaneServices.PROXY:
                            try:
                                content = json.loads(log["log"])
                            except json.JSONDecodeError:
                                # Store non JSON log
                                simple_logs.append(
                                    RuntimeLogDto(
                                        time=log["time"],
                                        created_at=timezone.now(),
                                        # Caddy put all logs into stderr, including info logs
                                        # So we just assume info logs
                                        level=RuntimeLogLevel.INFO,
                                        source=RuntimeLogSource.PROXY,
                                        container_id=log["container_id"],
                                        content=log["log"],
                                        content_text=escape_ansi(log["log"]),
                                    )
                                )
                            else:
                                log_serializer = HTTPServiceLogSerializer(data=content)
                                if log_serializer.is_valid():
                                    log_content = cast(dict, log_serializer.data)

                                    service_type = log_content.get("zane_service_type")
                                    service_id = log_content.get("zane_service_id")
                                    stack_id = log_content.get("zane_stack_id")
                                    registry_id = log_content.get("zane_registry_id")

                                    http_log: HttpLog | None = None

                                    if (
                                        service_id
                                        or stack_id
                                        or registry_id
                                        or service_type
                                        == ZaneProxyClient.ServiceType.ZANE_OPS
                                    ):
                                        match service_type:
                                            case ZaneProxyClient.ServiceType.ZANE_OPS:
                                                http_log = _build_http_log(
                                                    log["time"],
                                                    log_content,
                                                    source=ZaneProxyClient.ServiceType.ZANE_OPS,
                                                )

                                            case ZaneProxyClient.ServiceType.BUILD_REGISTRY:
                                                if registry_id:
                                                    http_log = _build_http_log(
                                                        log["time"],
                                                        log_content,
                                                        registry_id=registry_id,
                                                        source=ZaneProxyClient.ServiceType.BUILD_REGISTRY,
                                                    )

                                            case ZaneProxyClient.ServiceType.COMPOSE_STACK_SERVICE:
                                                stack_service_name = content.get(
                                                    "zane_stack_service_name"
                                                )
                                                if stack_service_name:
                                                    http_log = _build_http_log(
                                                        log["time"],
                                                        log_content,
                                                        stack_id=stack_id,
                                                        stack_service_name=stack_service_name,
                                                        source=ZaneProxyClient.ServiceType.COMPOSE_STACK_SERVICE,
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
                                                    http_log = _build_http_log(
                                                        log["time"],
                                                        log_content,
                                                        service_id=log_content.get(
                                                            "zane_service_id"
                                                        ),
                                                        deployment_id=deployment_id,
                                                        source=ZaneProxyClient.ServiceType.MANAGED_SERVICE,
                                                    )

                                    else:
                                        http_log = _build_http_log(
                                            log["time"],
                                            log_content,
                                            source=None,
                                        )

                                    if http_log:
                                        http_logs.append(http_log)
                                    continue

                                proxy_app_log_serializer = ProxyServiceLogSerializer(
                                    data=content
                                )
                                if proxy_app_log_serializer.is_valid():
                                    data = cast(dict, proxy_app_log_serializer.data)
                                    log_level_map: dict[
                                        str, Literal["INFO", "ERROR"]
                                    ] = {
                                        "debug": RuntimeLogLevel.INFO,
                                        "info": RuntimeLogLevel.INFO,
                                        "warn": RuntimeLogLevel.INFO,
                                        "error": RuntimeLogLevel.ERROR,
                                        "panic": RuntimeLogLevel.ERROR,
                                        "fatal": RuntimeLogLevel.ERROR,
                                    }
                                    simple_logs.append(
                                        RuntimeLogDto(
                                            time=log["time"],
                                            created_at=timezone.now(),
                                            level=log_level_map[data["level"]],
                                            source=RuntimeLogSource.PROXY,
                                            container_id=log["container_id"],
                                            content=log["log"],
                                            content_text=escape_ansi(log["log"]),
                                        )
                                    )

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
                                    container_id=log["container_id"],
                                    content=log["log"],
                                    content_text=escape_ansi(log["log"]),
                                )
                            )

                    stack_id = json_tag.get("zane.stack")
                    if stack_id is not None:
                        stack_service_name = json_tag.get("zane.stack.service")
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
                                stack_id=stack_id,
                                stack_service_name=stack_service_name,
                                container_id=log["container_id"],
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
    permission_classes = [HasWorkspace, IsWorkspaceMember]

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

        accessible_projects = get_accessible_projects(
            request.user,
            request.workspace,  # type: ignore
        )

        has_access = False

        condition = Q()
        if len(value) > 0:
            condition &= Q(**{f"{field}__startswith": value})

        if service_id:
            has_access = Service.objects.filter(
                id=service_id, project__id__in=accessible_projects
            ).exists()
            condition &= Q(service_id=service_id)

        if stack_id:
            has_access = ComposeStack.objects.filter(
                id=stack_id, project__id__in=accessible_projects
            ).exists()
            condition &= Q(stack_id=stack_id)

        if deployment_id:
            has_access = Deployment.objects.filter(
                hash=deployment_id, service__project__id__in=accessible_projects
            ).exists()
            condition &= Q(deployment_id=deployment_id)

        # The user does not have permission to access the logs for this service, stack or deployment
        if not has_access:
            condition &= Q(pk__in=[])

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
    permission_classes = [HasWorkspace, IsWorkspaceMember]

    def filter_queryset(self, queryset: QuerySet[HttpLog]):
        queryset = super().filter_queryset(queryset)

        service_id: str = self.request.query_params.get("service_id")  # type: ignore
        stack_id: str = self.request.query_params.get("stack_id")  # type: ignore
        deployment_id: str = self.request.query_params.get("deployment_id")  # type: ignore

        accessible_projects = get_accessible_projects(
            self.request.user,  # type: ignore
            self.request.workspace,  # type: ignore
        )

        has_access = False

        if service_id:
            has_access = Service.objects.filter(
                id=service_id, project__id__in=accessible_projects
            ).exists()

        if stack_id:
            has_access = ComposeStack.objects.filter(
                id=stack_id, project__id__in=accessible_projects
            ).exists()

        if deployment_id:
            has_access = Deployment.objects.filter(
                hash=deployment_id, service__project__id__in=accessible_projects
            ).exists()

        if not has_access:
            return queryset.filter(pk__in=[])

        return queryset

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
    permission_classes = [HasWorkspace, IsWorkspaceMember]

    def get_object(self):
        log: HttpLog = super().get_object()

        accessible_projects = get_accessible_projects(
            self.request.user,  # type: ignore
            self.request.workspace,  # type: ignore
        )

        has_access = False

        if log.service_id:
            has_access = Service.objects.filter(
                id=log.service_id, project__id__in=accessible_projects
            ).exists()

        if log.stack_id:
            has_access = ComposeStack.objects.filter(
                id=log.stack_id, project__id__in=accessible_projects
            ).exists()

        if log.deployment_id:
            has_access = Deployment.objects.filter(
                hash=log.deployment_id, service__project__id__in=accessible_projects
            ).exists()

        if not has_access:
            raise exceptions.NotFound()

        return log


class ServiceDeploymentRuntimeLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer
    permission_classes = [HasWorkspace, IsWorkspaceMember]

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
            project = Project.objects.get(
                slug=project_slug,
                id__in=get_accessible_projects(
                    self.request.user,  # type: ignore
                    self.request.workspace,  # type: ignore
                ),
            )

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
            if form.is_valid(raise_exception=True):
                search_client = LokiSearchClient(host=settings.LOKI_HOST)
                data = search_client.search(
                    query=dict(
                        **form.validated_data,  # type: ignore
                        deployment_id=deployment.hash,
                    )
                )
                return Response(data)


class ServiceDeploymentRuntimeLogsWithContextAPIView(APIView):
    serializer_class = RuntimeLogsContextSerializer
    permission_classes = [HasWorkspace, IsWorkspaceMember]

    @extend_schema(
        summary="Get deployment logs with context",
        parameters=[RuntimeLogsContextParamsSerializer],
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
        env_slug: str,
        time: str,
    ):
        try:
            project = Project.objects.get(
                slug=project_slug,
                id__in=get_accessible_projects(
                    self.request.user,  # type: ignore
                    self.request.workspace,  # type: ignore
                ),
            )

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

        search_client = LokiSearchClient(host=settings.LOKI_HOST)
        time_ns = int(time)

        form = RuntimeLogsContextParamsSerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        lines = cast(dict, form.validated_data).get("lines", 20)
        data = search_client.get_context(
            lines=math.ceil(lines / 2),
            timestamp_ns=time_ns,
            deployment_id=deployment.hash,
        )
        return Response(data)


class ServiceDeploymentBuildLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer
    permission_classes = [HasWorkspace, IsWorkspaceMember]

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
            project = Project.objects.get(
                slug=project_slug,
                id__in=get_accessible_projects(
                    self.request.user,  # type: ignore
                    self.request.workspace,  # type: ignore
                ),
            )

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
            if form.is_valid(raise_exception=True):
                search_client = LokiSearchClient(host=settings.LOKI_HOST)
                data = search_client.search(
                    query=dict(
                        **form.validated_data,  # type: ignore
                        deployment_id=deployment.hash,
                        source=[RuntimeLogSource.BUILD, RuntimeLogSource.SYSTEM],
                    )
                )
                return Response(data)
