from typing import Any, cast
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, ListAPIView

from .serializers import (
    ComposeStackSerializer,
    ComposeStackUpdateSerializer,
    ComposeStackDeployRequestSerializer,
    ComposeStackDeploymentSerializer,
    ComposeStackSnapshotSerializer,
    ComposeStackArchiveRequestSerializer,
    ComposeContentFieldChangeSerializer,
    ComposeEnvOverrideItemChangeSerializer,
    ComposeStackFieldChangeRequestSerializer,
    ComposeStackChangeSerializer,
    ComposeStackEnvOverrideSerializer,
)
from ..models import ComposeStack, ComposeStackDeployment, ComposeStackChange
from django.db.models import QuerySet
from rest_framework.views import APIView
from django.db import transaction

from zane_api.models import Project, Environment
from rest_framework import exceptions

from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, PolymorphicProxySerializer
from rest_framework import status
from temporal.workflows import DeployComposeStackWorkflow, ArchiveComposeStackWorkflow
from temporal.shared import ComposeStackDeploymentDetails, ComposeStackArchiveDetails
from temporal.client import TemporalClient
from ..dtos import ComposeStackSnapshot
from rest_framework.serializers import Serializer
from ..processor import ComposeSpecProcessor


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


class ComposeStackArchiveAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        responses={204: None},
        request=ComposeStackArchiveRequestSerializer,
        operation_id="archiveComposeStack",
        summary="Archive a compose stack",
    )
    def delete(self, request: Request, project_slug: str, env_slug: str, slug: str):
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

        form = ComposeStackArchiveRequestSerializer(data=request.data or {})
        form.is_valid(raise_exception=True)

        data = cast(dict[str, bool], form.data)

        snapshot_dict = cast(dict, ComposeStackSnapshotSerializer(stack).data)
        payload = ComposeStackArchiveDetails(
            stack=ComposeStackSnapshot.from_dict(snapshot_dict),
            delete_configs=data["delete_configs"],
            delete_volumes=data["delete_volumes"],
        )
        workflow_id = stack.archive_workflow_id

        def commit_callback():
            TemporalClient.start_workflow(
                ArchiveComposeStackWorkflow.run,
                arg=payload,
                id=workflow_id,
            )

        transaction.on_commit(commit_callback)

        stack.delete()
        stack.name

        return Response(status=status.HTTP_204_NO_CONTENT)


class ComposeStackDeployAPIView(APIView):
    serializer_class = ComposeStackDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=ComposeStackDeployRequestSerializer,
        operation_id="deployComposeStack",
        summary="Queue a new deployment for the compose stack",
    )
    def put(self, request: Request, project_slug: str, env_slug: str, slug: str):
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
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class ComposeStackRequestChanges(APIView):
    serializer_class = ComposeStackChangeSerializer

    @transaction.atomic()
    @extend_schema(
        request=PolymorphicProxySerializer(
            component_name="ComposeStackDeploymentChangeRequest",
            resource_type_field_name="field",
            serializers=[
                ComposeContentFieldChangeSerializer,
                ComposeEnvOverrideItemChangeSerializer,
            ],
        ),
        operation_id="requestComposeStackUpdate",
        summary="Request a new compose stack change",
    )
    def put(self, request: Request, project_slug: str, env_slug: str, slug: str):
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

        field_serializer_map = {
            ComposeStackChange.ChangeField.ENV_OVERRIDES: ComposeEnvOverrideItemChangeSerializer,
            ComposeStackChange.ChangeField.COMPOSE_CONTENT: ComposeContentFieldChangeSerializer,
        }

        request_serializer = ComposeStackFieldChangeRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        form_serializer_class: type[Serializer] = field_serializer_map[
            cast(dict, request_serializer.data)["field"]
        ]
        form = form_serializer_class(data=request.data, context={"stack": stack})
        form.is_valid(raise_exception=True)

        data = cast(dict, form.data)
        field = data["field"]
        new_value: dict | None = data.get("new_value")
        item_id = data.get("item_id")
        change_type = data.get("type")
        old_value: Any = None
        match field:
            case ComposeStackChange.ChangeField.COMPOSE_CONTENT:
                old_value = getattr(stack, field)
            case ComposeStackChange.ChangeField.ENV_OVERRIDES:
                if change_type in ["UPDATE", "DELETE"]:
                    old_value = ComposeStackEnvOverrideSerializer(
                        stack.env_overrides.get(id=item_id)
                    ).data

        change = ComposeStackChange(
            type=change_type,
            field=field,
            old_value=old_value,
            new_value=new_value,
            stack=stack,
            item_id=item_id,
        )
        if new_value != old_value:
            change = stack.add_change(change)

        serializer = ComposeStackChangeSerializer(change)

        return Response(data=serializer.data)
