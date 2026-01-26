from typing import cast
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from search.loki_client import LokiSearchClient
from search.serializers import RuntimeLogsSearchSerializer, RuntimeLogsContextSerializer

from zane_api.models import Environment, Project
from .serializers import StackRuntimeLogsQuerySerializer, StackBuildLogsQuerySerializer, StackRuntimeLogsContextQuerySerializer
from ..models import ComposeStack
from search.dtos import RuntimeLogSource


class ComposeStackRuntimeLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer

    @extend_schema(
        summary="Get stack runtime logs", parameters=[StackRuntimeLogsQuerySerializer]
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        env_slug: str,
        slug: str,
    ):
        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(),
                project=project,
            )
            stack = ComposeStack.objects.get(
                environment=environment,
                project=project,
                slug=slug,
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except ComposeStack.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A compose stack with the slug `{slug}` does not exist in this environment"
            )

        form = StackRuntimeLogsQuerySerializer(data=request.query_params)
        if form.is_valid(raise_exception=True):
            print(f"{form.validated_data=}")
            search_client = LokiSearchClient(host=settings.LOKI_HOST)
            data = search_client.search(
                query=dict(**form.validated_data, stack_id=stack.id),  # type: ignore
            )
            return Response(data)


class ComposeStackBuildLogsAPIView(APIView):
    serializer_class = RuntimeLogsSearchSerializer

    @extend_schema(
        summary="Get stack build logs", parameters=[StackBuildLogsQuerySerializer]
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        env_slug: str,
        slug: str,
    ):
        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(),
                project=project,
            )
            stack = ComposeStack.objects.get(
                environment=environment,
                project=project,
                slug=slug,
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except ComposeStack.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A compose stack with the slug `{slug}` does not exist in this environment"
            )

        form = StackBuildLogsQuerySerializer(data=request.query_params)
        print(f"{request.query_params=}")
        if form.is_valid(raise_exception=True):
            search_client = LokiSearchClient(host=settings.LOKI_HOST)
            data = search_client.search(
                query=dict(
                    **form.validated_data,  # type: ignore
                    stack_id=stack.id,
                    source=[RuntimeLogSource.BUILD, RuntimeLogSource.SYSTEM],
                )
            )
            return Response(data)


class ComposeStackRuntimeLogsWithContextAPIView(APIView):
    serializer_class = RuntimeLogsContextSerializer

    @extend_schema(
        summary="Get stack runtime logs with context",
        parameters=[StackRuntimeLogsContextQuerySerializer],
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        env_slug: str,
        slug: str,
        time: str,
    ):
        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(),
                project=project,
            )
            stack = ComposeStack.objects.get(
                environment=environment,
                project=project,
                slug=slug,
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except ComposeStack.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A compose stack with the slug `{slug}` does not exist in this environment"
            )

        form = StackRuntimeLogsContextQuerySerializer(data=request.query_params)
        if form.is_valid(raise_exception=True):
            search_client = LokiSearchClient(host=settings.LOKI_HOST)
            time_ns = int(time)
            data = search_client.get_context(
                timestamp_ns=time_ns,
                stack_id=stack.id,
                stack_service_names=form.validated_data.get("stack_service_names"),  # type: ignore
            )
            return Response(data)
