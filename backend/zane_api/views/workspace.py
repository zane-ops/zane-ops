from typing import cast

from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import (
    ListAPIView,
    CreateAPIView,
    UpdateAPIView,
    RetrieveDestroyAPIView,
)

from rest_framework import status


from ..models import Workspace, WorkspaceMembership, WorkspaceRole
from ..constants import WORKSPACE_SESSION_KEY
from .serializers import (
    SwitchWorkspaceRequestSerializer,
    WorkspaceEditPermissionsRequestSerializer,
    WorkspaceTransferOwnershipResponseSerializer,
    WorkspaceTransferOwnershipRequestSerializer,
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
from .base import ResourceConflict, BadRequest
from django.db import transaction


class WorkspaceMemberDetailAPIView(RetrieveDestroyAPIView):
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

    def perform_destroy(self, instance: WorkspaceMembership):
        current_membership = WorkspaceMembership.objects.get(
            workspace=self.request.workspace,  # type: ignore
            user=self.request.user,
        )

        if instance.user == self.request.user:
            raise ResourceConflict(
                "You cannot remove yourself from the workspace. Contact the owner to remove you from the workspace."
            )

        # We don't need to check for the case of removing another owner
        # as there are DB checks that enforces that a workspace can only
        # have one owner
        if (
            current_membership.role < WorkspaceRole.OWNER
            and instance.role >= WorkspaceRole.ADMIN
        ):
            raise ResourceConflict(
                "You cannot remove another admin or the owner of the workspace."
            )

        return super().perform_destroy(instance)


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


class WorkspaceLeaveAPIView(APIView):
    @extend_schema(
        responses={204: None},
        operation_id="leaveWorkspace",
        summary="Leave workspace",
    )
    def post(self, request: Request):
        membership = WorkspaceMembership.objects.get(
            user=self.request.user,
            workspace=self.request.workspace,  # type: ignore
        )

        if membership.role == WorkspaceRole.OWNER:
            raise ResourceConflict(
                "You cannot leave this workspace, to be able to do so, please transfer ownership to another member."
            )
        membership.delete()

        last_membership = (
            WorkspaceMembership.objects.filter(
                user=self.request.user,
            )
            .exclude(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("workspace")
            .first()
        )

        request.session[WORKSPACE_SESSION_KEY] = (
            last_membership.workspace.id if last_membership is not None else None
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceTransferOwnershipAPIView(APIView):
    permission_classes = [HasWorkspace, IsWorkspaceOwner]
    serializer_class = WorkspaceTransferOwnershipResponseSerializer

    @transaction.atomic()
    @extend_schema(
        request=WorkspaceTransferOwnershipRequestSerializer,
        operation_id="transferWorkspaceOwnership",
        summary="Transfer workspace ownership",
    )
    def post(self, request: Request):
        form = WorkspaceTransferOwnershipRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        try:
            new_owner_membership = WorkspaceMembership.objects.get(
                pk=data["new_owner_id"],
                workspace=self.request.workspace,  # type: ignore
            )
        except WorkspaceMembership.DoesNotExist:
            raise exceptions.NotFound("This user is not a member of this workspace.")

        if new_owner_membership.role < WorkspaceRole.ADMIN:
            raise ResourceConflict(
                "You cannot transfer ownership to a non-admin member. Promote them to admin first."
            )

        if new_owner_membership.user == self.request.user:
            raise ResourceConflict("You are already the owner of this workspace.")

        WorkspaceMembership.objects.filter(
            user=self.request.user,
            workspace=self.request.workspace,  # type: ignore
        ).update(role=WorkspaceRole.ADMIN)

        WorkspaceMembership.objects.filter(
            pk=data["new_owner_id"],
            workspace=self.request.workspace,  # type: ignore
        ).update(role=WorkspaceRole.OWNER)

        serializer = WorkspaceTransferOwnershipResponseSerializer({"success": True})
        return Response(serializer.data)
