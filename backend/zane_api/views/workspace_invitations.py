from typing import cast

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, DestroyAPIView, RetrieveAPIView
from rest_framework import status, permissions

from .base import ResourceConflict


from ..models import WorkspaceMembership, WorkspaceInvitation
from rest_framework import exceptions
from ..serializers import (
    WorkspaceInvitationSerializer,
    WorkspaceMemberSerializer,
    WorkspaceInvitationLinkSerializer,
)
from ..permissions import (
    HasWorkspace,
    IsWorkspaceAdmin,
)
import secrets
from django.db.models import QuerySet
from django.utils import timezone
from datetime import timedelta
from .serializers import (
    RegenerateWorkspaceInvitationRequestSerializer,
    InviteUserIntoWorkspaceRequestSerializer,
)


class ListWorkspaceInvitationAPIView(ListAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer

    def get_queryset(self) -> QuerySet[WorkspaceInvitation]:  # type: ignore
        return WorkspaceInvitation.objects.filter(
            workspace=self.request.workspace  # type: ignore
        ).prefetch_related("accessible_projects")


class ListWorkspaceMembersAPIView(ListAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceMemberSerializer

    def get_queryset(self) -> QuerySet[WorkspaceInvitation]:  # type: ignore
        return (
            WorkspaceMembership.objects.filter(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("user")
            .prefetch_related("accessible_projects")
        )


class RegenerateWorkspaceInvitationAPIView(APIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer

    @extend_schema(
        request=RegenerateWorkspaceInvitationRequestSerializer,
        operation_id="regenerateUserInvitation",
        summary="Regenerate user invitation link in workspace",
    )
    def put(self, request: Request, id: str):
        try:
            invitation = (
                WorkspaceInvitation.objects.filter(
                    pk=id,
                    workspace=self.request.workspace,  # type: ignore
                )
                .prefetch_related("accessible_projects")
                .get()
            )
        except WorkspaceInvitation.DoesNotExist:
            raise exceptions.NotFound(
                f"An invitation with an id of `{id}` does not exist in this workspace."
            )

        form = RegenerateWorkspaceInvitationRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(dict, form.data)

        valid_for = data["valid_for"]
        invitation.token = secrets.token_hex(16)
        invitation.expires_at = timezone.now() + timedelta(days=valid_for)
        invitation.save()

        serializer = WorkspaceInvitationSerializer(invitation)
        return Response(data=serializer.data)


class WorkspaceInvitationDeleteAPIView(DestroyAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer
    queryset = WorkspaceInvitation.objects.all()
    lookup_field = "id"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return super().get_queryset().filter(workspace=self.request.workspace)


class WorkspaceInvitationLinkDetailsAPIView(RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = WorkspaceInvitationLinkSerializer
    queryset = WorkspaceInvitation.objects.all().select_related("workspace")
    lookup_field = "token"
    lookup_url_kwarg = "token"


class InviteUserIntoWorkspaceAPIView(APIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer

    @extend_schema(
        request=InviteUserIntoWorkspaceRequestSerializer,
        operation_id="inviteUser",
        summary="Generate an invitation link for a new user in a workspace",
    )
    def post(self, request):
        form = InviteUserIntoWorkspaceRequestSerializer(
            data=request.data,
            context=dict(
                workspace=self.request.workspace,  # type: ignore
            ),
        )
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        accessible_projects = data["accessible_project_ids"]

        try:
            invitation = WorkspaceInvitation.objects.create(
                token=secrets.token_hex(16),
                username=data["username"],
                role=data["role"],
                expires_at=timezone.now() + timedelta(days=data["valid_for"]),
                workspace=self.request.workspace,  # type: ignore
            )
        except IntegrityError:
            raise ResourceConflict(
                detail=(
                    "A pending invitation already exists for this user. "
                    "Update or cancel it before sending a new one."
                )
            )

        invitation.accessible_projects.add(*accessible_projects)

        serializer = WorkspaceInvitationSerializer(invitation)
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)
