from typing import cast

from drf_spectacular.utils import extend_schema

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.views import APIView

from rest_framework import exceptions
from temporal.client import TemporalClient
from temporal.shared import (
    ArchivedProjectDetails,
    EnvironmentDetails,
    ComposeStackArchiveDetails,
)
from temporal.workflows import RemoveProjectResourcesWorkflow

from zane_api.models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    ArchivedProject,
    Service,
    PortConfiguration,
    Volume,
    URL,
    Config,
    ArchivedDockerService,
    ArchivedGitService,
)
from zane_api.constants import WORKSPACE_SESSION_KEY
from zane_api.permissions import IsInstanceOwner
from zane_api.serializers import WorkspaceSerializer

from .serializers import WorkspaceListFilterSet
from ..serializers import (
    WorkspaceDetailSerializer,
    WorkspaceTransferOwnershipSerializer,
)
from zane_api.views.base import (
    DefaultPageNumberPagination,
    EMPTY_PAGINATED_RESPONSE,
    ResourceConflict,
)
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

User = get_user_model()


class ListWorkspacesAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.all()
    pagination_class = DefaultPageNumberPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = WorkspaceListFilterSet

    @extend_schema(
        summary="List all workspaces in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e


class WorkspaceDetailAPIView(RetrieveDestroyAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceDetailSerializer
    lookup_field = "pk"
    lookup_url_kwarg = "id"

    def get_queryset(self):  # type: ignore
        return Workspace.objects.prefetch_related(
            # No need to prefetch `memberships` as it's already implied
            # when doing `memberships__{table}`
            "memberships__user",
            "memberships__accessible_projects",
        )

    def get_object(self) -> Workspace:  # type: ignore
        return super().get_object()

    @transaction.atomic()
    def perform_destroy(self, instance: Workspace):
        workflow_payloads: list[tuple[ArchivedProjectDetails, str]] = []

        for project in instance.projects.all():
            archived_version = ArchivedProject.get_or_create_from_project(project)

            docker_service_list = (
                Service.objects.filter(Q(project=project))
                .select_related("project", "healthcheck")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "deployments"
                )
            )
            id_list = []
            for service in docker_service_list:
                if service.deployments.count() > 0:
                    if service.type == Service.ServiceType.DOCKER_REGISTRY:
                        ArchivedDockerService.create_from_service(
                            service, archived_version
                        )
                    else:
                        ArchivedGitService.create_from_service(
                            service, archived_version
                        )
                    id_list.append(service.id)

            PortConfiguration.objects.filter(Q(service__id__in=id_list)).delete()
            URL.objects.filter(Q(service__id__in=id_list)).delete()
            Volume.objects.filter(Q(service__id__in=id_list)).delete()
            Config.objects.filter(Q(service__id__in=id_list)).delete()
            for service in docker_service_list:
                if service.healthcheck is not None:
                    service.healthcheck.delete()
            # Delete Preview metadata before the services because they hold protected references
            # to the services
            for env in project.environments.filter().select_related("preview_metadata"):
                if env.preview_metadata is not None:
                    env.preview_metadata.delete()
            docker_service_list.delete()

            workflow_payloads.append(
                (
                    ArchivedProjectDetails(
                        id=archived_version.pk,
                        original_id=archived_version.original_id,
                        environments=[
                            EnvironmentDetails(
                                id=env.original_id,
                                name=env.name,
                                project_id=archived_version.original_id,
                            )
                            for env in archived_version.environments.all()
                        ],
                        compose_stacks=[
                            ComposeStackArchiveDetails(stack=stack.snapshot)
                            for stack in project.compose_stacks.filter(
                                user_content__isnull=False
                            )
                            .prefetch_related("env_overrides")
                            .all()
                        ],
                    ),
                    archived_version.workflow_id,
                )
            )

        def commit_callback():
            for payload, workflow_id in workflow_payloads:
                TemporalClient.start_workflow(
                    RemoveProjectResourcesWorkflow.run,
                    payload,
                    id=workflow_id,
                )

        transaction.on_commit(commit_callback)

        return super().perform_destroy(instance)

    @extend_schema(summary="Delete a workspace (admin)")
    def delete(self, request: Request, *args, **kwargs):
        workspace_id = self.get_object().id

        response = super().delete(request, *args, **kwargs)

        # If the instance owner was currently in the deleted workspace,
        # switch their session to another workspace they are a member of
        if request.session.get(WORKSPACE_SESSION_KEY) == workspace_id:
            last_membership = (
                WorkspaceMembership.objects.filter(
                    user=request.user,
                )
                .exclude(workspace_id=workspace_id)
                .select_related("workspace")
                .first()
            )
            request.session[WORKSPACE_SESSION_KEY] = (
                last_membership.workspace.id if last_membership is not None else None
            )

        return response


class WorkspaceTransferOwnershipAPIView(APIView):
    permission_classes = [IsInstanceOwner]

    @transaction.atomic()
    @extend_schema(
        responses=WorkspaceDetailSerializer,
        request=WorkspaceTransferOwnershipSerializer,
        operation_id="consoleTransferWorkspaceOwnership",
        summary="Transfer workspace ownership (admin)",
    )
    def put(self, request: Request, id: str):
        try:
            workspace = Workspace.objects.filter(pk=id).get()
        except Workspace.DoesNotExist:
            raise exceptions.NotFound(f"Workspace with `id={id}` does not exist.")

        form = WorkspaceTransferOwnershipSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(dict, form.validated_data)

        new_owner = User.objects.get(pk=data["owner_id"])

        new_owner_membership = WorkspaceMembership.objects.filter(
            user=new_owner,
            workspace=workspace,
        ).first()

        if new_owner_membership is None:
            new_owner_membership = WorkspaceMembership(
                user=new_owner,
                workspace=workspace,
            )
        elif new_owner_membership.role == WorkspaceRole.OWNER:
            raise ResourceConflict("This user is already the owner of the workspace")

        # Update the previous owner
        WorkspaceMembership.objects.filter(
            workspace=workspace, role=WorkspaceRole.OWNER
        ).update(role=WorkspaceRole.ADMIN)

        # Change ownership
        new_owner_membership.role = WorkspaceRole.OWNER
        new_owner_membership.save()

        serializer = WorkspaceDetailSerializer(workspace)
        return Response(serializer.data)
