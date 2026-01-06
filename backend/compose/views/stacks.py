from typing import cast
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, ListAPIView
from .serializers import (
    ComposeStackSerializer,
    ComposeStackUpdateSerializer,
    ComposeStackDeployRequestSerializer,
    ComposeStackDeploymentSerializer,
    ComposeStackSnapshotSerializer,
)
from ..models import ComposeStack, ComposeStackDeployment
from django.db.models import QuerySet
from rest_framework.views import APIView
from django.db import transaction

from zane_api.models import Project, Environment
from rest_framework import exceptions

from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework import status
from temporal.workflows import DeployComposeStackWorkflow
from temporal.shared import ComposeStackDeploymentDetails
from temporal.client import TemporalClient


class ComposeStackListAPIView(ListAPIView):
    serializer_class = ComposeStackSerializer
    queryset = ComposeStack.objects.all()
    pagination_class = None

    def get_queryset(self) -> QuerySet[ComposeStack]:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]

        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )

        return (
            ComposeStack.objects.filter(
                environment=environment,
                project=project,
            )
            .all()
            .prefetch_related("changes")
        )


class ComposeStackCreateAPIView(CreateAPIView):
    serializer_class = ComposeStackSerializer
    queryset = ComposeStack.objects.all()

    def get_queryset(self) -> QuerySet[ComposeStack]:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]

        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )

        return (
            ComposeStack.objects.filter(
                environment=environment,
                project=project,
            )
            .all()
            .prefetch_related("changes")
        )

    def get_serializer_context(self):
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]

        try:
            project = Project.objects.get(
                slug=project_slug.lower(), owner=self.request.user
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )

        return dict(
            **super().get_serializer_context(),
            project=project,
            environment=environment,
        )


class ComposeStackDetailsAPIView(RetrieveUpdateAPIView):
    serializer_class = ComposeStackUpdateSerializer
    lookup_field = "slug"
    http_method_names = ["get", "put"]

    def get_object(self) -> ComposeStack:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]
        slug = self.kwargs["slug"]

        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            stack = (
                ComposeStack.objects.filter(
                    environment=environment,
                    project=project,
                    slug=slug,
                )
                .prefetch_related("changes", "env_overrides")
                .get()
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

        return stack


class ComposeStackDeployAPIView(APIView):
    serializer_class = ComposeStackDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=ComposeStackDeployRequestSerializer,
        operation_id="deployComposeStack",
        summary="Queue a new deployment for the compose stack",
    )
    def post(self, request: Request, project_slug: str, env_slug: str, slug: str):
        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            stack = (
                ComposeStack.objects.filter(
                    environment=environment,
                    project=project,
                    slug=slug,
                )
                .prefetch_related("changes", "env_overrides")
                .get()
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

        form = ComposeStackDeployRequestSerializer(data=request.data or {})
        form.is_valid(raise_exception=True)

        data = cast(dict[str, str], form.data)
        deployment = ComposeStackDeployment.objects.create(
            commit_message=data["commit_message"],
            stack=stack,
        )

        stack.apply_pending_changes(deployment=deployment)

        deployment.stack_snapshot = ComposeStackSnapshotSerializer(stack).data  # type: ignore
        deployment.save()

        payload = ComposeStackDeploymentDetails.from_deployment(deployment=deployment)

        def commit_callback():
            TemporalClient.start_workflow(
                DeployComposeStackWorkflow.run,
                arg=payload,
                id=deployment.workflow_id,
            )

        transaction.on_commit(commit_callback)

        serializer = ComposeStackDeploymentSerializer(deployment)
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)
