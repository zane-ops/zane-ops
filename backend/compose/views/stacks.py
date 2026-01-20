from typing import Any, cast
from rest_framework.generics import (
    CreateAPIView,
    RetrieveUpdateAPIView,
    ListAPIView,
    RetrieveAPIView,
)

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
    CreateComposeStackFromDokployTemplateRequestSerializer,
    CreateComposeStackFromDokployTemplateObjectRequestSerializer,
    ComposeStackToggleRequestSerializer,
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
from temporal.workflows import (
    DeployComposeStackWorkflow,
    ArchiveComposeStackWorkflow,
    ToggleComposeStackWorkflow,
)
from temporal.shared import (
    ComposeStackDeploymentDetails,
    ComposeStackArchiveDetails,
    CancelDeploymentSignalInput,
    ToggleComposeStackDetails,
)
from temporal.client import TemporalClient
from zane_api.views.base import ResourceConflict
from zane_api.serializers import ErrorResponse409Serializer
from ..dtos import ComposeStackSnapshot, DokployTemplate
from rest_framework.serializers import Serializer
from ..adapters import DokployComposeAdapter
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


class ComposeStackCreateFromDokployBase64APIView(APIView):
    @transaction.atomic()
    @extend_schema(
        operation_id="createFromDokployTemplateBase64",
        request=CreateComposeStackFromDokployTemplateRequestSerializer,
        responses={201: ComposeStackSerializer},
        summary="Create compose stack from Dokploy template",
        description="Use a dokploy template encoded as base64 and ZaneOps will automatically convert it to its compose syntax",
    )
    def post(self, request: Request, project_slug: str, env_slug: str):
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

        form = CreateComposeStackFromDokployTemplateRequestSerializer(
            data=request.data,
            context=dict(
                environment=environment,
                project=project,
            ),
        )
        form.is_valid(raise_exception=True)

        data = cast(dict, form.data)
        stack = ComposeStack.objects.create(
            slug=data["slug"],
            environment=environment,
            project=project,
            network_alias_prefix=f"zn-{data['slug']}",
        )

        user_content = DokployComposeAdapter.to_zaneops(template=data["user_content"])

        changes = [
            ComposeStackChange(
                stack=stack,
                type=ComposeStackChange.ChangeType.UPDATE,
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                new_value=user_content,
            )
        ]

        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=user_content,
            stack=stack,
        )

        changes.extend(
            [
                ComposeStackChange(
                    stack=stack,
                    field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
                    type=ComposeStackChange.ChangeType.ADD,
                    new_value=override_data.to_dict(),
                )
                for override_data in artifacts.env_overrides
            ]
        )

        stack.changes.bulk_create(changes)

        response = ComposeStackSerializer(stack)
        return Response(data=response.data, status=status.HTTP_201_CREATED)


class ComposeStackCreateFromDokployObjectAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        operation_id="createFromDokployTemplateObject",
        request=CreateComposeStackFromDokployTemplateObjectRequestSerializer,
        responses={201: ComposeStackSerializer},
        summary="Create compose stack from Dokploy template object (compose+config)",
        description="Pass a dokploy object with content+config and ZaneOps will automatically convert it to its compose syntax",
    )
    def post(self, request: Request, project_slug: str, env_slug: str):
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

        form = CreateComposeStackFromDokployTemplateObjectRequestSerializer(
            data=request.data,
            context=dict(
                environment=environment,
                project=project,
            ),
        )
        form.is_valid(raise_exception=True)

        data = cast(dict, form.data)
        stack = ComposeStack.objects.create(
            slug=data["slug"],
            environment=environment,
            project=project,
            network_alias_prefix=f"zn-{data['slug']}",
        )

        template = DokployTemplate(**data)

        user_content = DokployComposeAdapter.to_zaneops(template=template.base64)

        changes = [
            ComposeStackChange(
                stack=stack,
                type=ComposeStackChange.ChangeType.UPDATE,
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                new_value=user_content,
            )
        ]

        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=user_content,
            stack=stack,
        )

        changes.extend(
            [
                ComposeStackChange(
                    stack=stack,
                    field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
                    type=ComposeStackChange.ChangeType.ADD,
                    new_value=override_data.to_dict(),
                )
                for override_data in artifacts.env_overrides
            ]
        )

        stack.changes.bulk_create(changes)

        response = ComposeStackSerializer(stack)
        return Response(data=response.data, status=status.HTTP_201_CREATED)


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
    queryset = ComposeStack.objects.all()

    @extend_schema(
        operation_id="getComposeStackDetails",
        summary="Get a compose stack details",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

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

        if stack.deployments.count() > 0:
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


class ComposeStackDeploymentDetailsAPIView(RetrieveAPIView):
    serializer_class = ComposeStackDeploymentSerializer
    lookup_field = "hash"
    queryset = ComposeStackDeployment.objects.all()

    @extend_schema(
        operation_id="getComposeStackDeploymentDetails",
        summary="Get a compose stack deployment details",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self) -> ComposeStackDeployment:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]
        slug = self.kwargs["slug"]
        hash = self.kwargs["hash"]

        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            stack = ComposeStack.objects.filter(
                environment=environment,
                project=project,
                slug=slug,
            ).get()
            deployment = (
                ComposeStackDeployment.objects.filter(stack=stack, hash=hash)
                .prefetch_related("changes")
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
        except ComposeStackDeployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A compose stack deployment with the hash `{hash}` does not exist in this stack"
            )

        return deployment


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
        new_value: dict | str | None = data.get("new_value")
        item_id = data.get("item_id")
        change_type = data.get("type")
        old_value: Any = None
        match field:
            case ComposeStackChange.ChangeField.COMPOSE_CONTENT:
                old_value = stack.user_content
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


class CancelComposeStackDeploymentAPIView(APIView):
    serializer_class = ComposeStackDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=None,
        responses={
            409: ErrorResponse409Serializer,
            200: ComposeStackDeploymentSerializer,
        },
        operation_id="cancelComposeStackDeployment",
        summary="Cancel compose stack deployment",
        description="Cancel a compose stack deployment in progress.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        env_slug: str,
        slug: str,
        hash: str,
    ):
        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=request.user,
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            stack = ComposeStack.objects.filter(
                environment=environment,
                project=project,
                slug=slug,
            ).get()
            deployment = (
                ComposeStackDeployment.objects.filter(stack=stack, hash=hash)
                .select_related("stack")
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
        except ComposeStackDeployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{hash}` does not exist for this stack."
            )

        if deployment.finished_at is not None or deployment.status not in [
            ComposeStackDeployment.DeploymentStatus.QUEUED,
            ComposeStackDeployment.DeploymentStatus.DEPLOYING,
        ]:
            raise ResourceConflict(
                detail="This deployment cannot be cancelled as it has already finished "
                "or is in the process of cancelling."
            )

        if deployment.started_at is None:
            deployment.status = ComposeStackDeployment.DeploymentStatus.CANCELLED
            deployment.status_reason = "Deployment cancelled."
            deployment.save()

        # Capture values before lambda to avoid lazy loading issues after commit
        deployment_hash = deployment.hash
        workflow_id = deployment.workflow_id

        transaction.on_commit(
            lambda: TemporalClient.workflow_signal(
                workflow=DeployComposeStackWorkflow.run,
                input=CancelDeploymentSignalInput(deployment_hash=deployment_hash),
                signal=DeployComposeStackWorkflow.cancel,
                workflow_id=workflow_id,
            )
        )

        serializer = ComposeStackDeploymentSerializer(deployment)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class ToggleComposeStackAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        request=ComposeStackToggleRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            202: None,
        },
        operation_id="toggleComposeStack",
        summary="Stop/Start a compose stack",
        description="Stops all services in a compose stack (scales to 0) or starts them back up.",
    )
    def put(self, request: Request, project_slug: str, env_slug: str, slug: str):
        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=request.user,
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
                .prefetch_related("deployments")
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

        form = ComposeStackToggleRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(dict[str, str], form.data)

        # Check if stack has at least one deployment
        if (
            stack.deployments.exclude(
                status=ComposeStackDeployment.DeploymentStatus.FAILED
            ).count()
            == 0
        ):
            raise ResourceConflict(
                detail="This stack has not been succesfully deployed yet, and thus its state cannot be toggled."
            )

        snapshot_dict = cast(dict, ComposeStackSnapshotSerializer(stack).data)
        snapshot = ComposeStackSnapshot.from_dict(snapshot_dict)

        payload = ToggleComposeStackDetails(
            stack=snapshot,
            desired_state=data["desired_state"],  # type: ignore
        )

        # Capture id before lambda
        workflow_id = stack.toggle_workflow_id

        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                workflow=ToggleComposeStackWorkflow.run,
                arg=payload,
                id=workflow_id,
            )
        )

        return Response(None, status=status.HTTP_202_ACCEPTED)
