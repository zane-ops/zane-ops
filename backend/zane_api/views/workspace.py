from typing import cast

from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import (
    ListAPIView,
    CreateAPIView,
    UpdateAPIView,
    RetrieveAPIView,
)

from rest_framework import status


from ..models import Workspace, WorkspaceMembership, WorkspaceRole
from ..constants import WORKSPACE_SESSION_KEY
from .serializers import (
    SwitchWorkspaceRequestSerializer,
    WorkspaceEditPermissionsRequestSerializer,
)
from rest_framework import exceptions
from ..serializers import (
    WorkspaceMembershipSerializer,
    WorkspaceSerializer,
    WorkspaceMemberSerializer,
)
from ..permissions import (
    IsInstanceOwner,
    HasWorkspace,
    IsWorkspaceOwner,
    IsWorkspaceAdmin,
)

from django.db.models import QuerySet
from .base import ResourceConflict
from django.db import transaction


class WorkspaceMemberDetailAPIView(RetrieveAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceMemberSerializer
    lookup_field = "pk"
    lookup_url_kwarg = "membership_id"

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return (
            WorkspaceMembership.objects.filter(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("user")
            .prefetch_related("accessible_projects")
        )


class EditWorkspaceMemberPermissionsAPIView(APIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceMemberSerializer

    @transaction.atomic()
    @extend_schema(
        request=WorkspaceEditPermissionsRequestSerializer,
        operation_id="editWorkpacePermissions",
        summary="Edit workspace membership permissions",
    )
    def put(self, request: Request, membership_id: int):
        try:
            membership = (
                WorkspaceMembership.objects.filter(
                    workspace=self.request.workspace,  # type: ignore
                    id=membership_id,
                )
                .select_related("user")
                .prefetch_related("accessible_projects")
                .get()
            )
        except WorkspaceMembership.DoesNotExist:
            raise exceptions.NotFound()

        if membership.user == self.request.user:
            raise ResourceConflict(
                "You cannot edit your own permissions in the workspace."
            )

        form = WorkspaceEditPermissionsRequestSerializer(
            data=request.data,
            context=dict(
                workspace=self.request.workspace  # type: ignore
            ),
        )
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        membership.role = data["role"]
        membership.save()

        membership.accessible_projects.clear()
        for project in data["accessible_project_ids"]:
            membership.accessible_projects.add(project)

        serializer = WorkspaceMemberSerializer(membership)
        return Response(serializer.data)


class ListWorkspaceMembersAPIView(ListAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceMemberSerializer

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return (
            WorkspaceMembership.objects.filter(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("user")
            .prefetch_related("accessible_projects")
        )


class WorkspaceMembershipListAPIView(ListAPIView):
    serializer_class = WorkspaceMembershipSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return WorkspaceMembership.objects.filter(
            user=self.request.user
        ).select_related("workspace")


class EditWorkspaceAPIView(UpdateAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceOwner]
    serializer_class = WorkspaceSerializer
    http_method_names = ["put"]

    def get_object(self) -> Workspace:  # type: ignore
        return self.request.workspace  # type: ignore


class CreateWorkspaceAPIView(CreateAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceSerializer

    def perform_create(self, serializer: WorkspaceSerializer):
        super().perform_create(serializer)

        WorkspaceMembership.objects.create(
            user=self.request.user,
            workspace=serializer.instance,
            role=WorkspaceRole.OWNER,
        )

    @extend_schema(
        operation_id="createWorkspace",
        summary="Create a new workspace",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SwitchWorkspaceAPIView(APIView):
    @extend_schema(
        request=SwitchWorkspaceRequestSerializer,
        responses={
            204: None,
        },
        operation_id="switchWorkspace",
        summary="Switch workspaces",
    )
    def post(self, request: Request) -> Response:
        form = SwitchWorkspaceRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(dict, form.data)

        workspace_id = data.get("workspace_id")

        workspace = Workspace.objects.filter(
            memberships__user=request.user,
            id=workspace_id,
        ).first()

        if workspace is None:
            raise exceptions.NotFound(detail="Workspace not found")

        request.session[WORKSPACE_SESSION_KEY] = workspace.id

        return Response(status=status.HTTP_204_NO_CONTENT)
