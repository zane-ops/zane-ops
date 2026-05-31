from typing import cast

from django.db import IntegrityError
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

from .base import ResourceConflict


from ..models import Workspace, WorkspaceMembership, WorkspaceRole, WorkspaceInvitation
from rest_framework import exceptions
from ..serializers import WorkspaceInvitationSerializer, WorkspaceMemberSerializer
from ..permissions import (
    HasWorkspace,
    IsWorkspaceAdmin,
)
import secrets
from django.db.models import QuerySet
from django.utils import timezone
from datetime import timedelta


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


class WorkspaceInvitationDetailsAPIView(RetrieveDestroyAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer
    queryset = WorkspaceInvitation.objects.all()
    lookup_field = "id"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return super().get_queryset().filter(workspace=self.request.workspace)


class InviteUserIntoWorkspaceAPIView(CreateAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer

    def get_serializer_context(self):
        return dict(
            **super().get_serializer_context(),
            workspace=(
                self.request.workspace  # type: ignore
                # This mumbo jumbo is needed because the OpenAPI generator runs this
                # function and it doesn't have a correctly initialized request at
                # generation time
                if hasattr(self.request, "workspace")
                else None
            ),
        )

    def perform_create(self, serializer: WorkspaceInvitationSerializer):
        accessible_projects = cast(dict, serializer.validated_data).pop(
            "accessible_project_ids", []
        )
        valid_for = cast(dict, serializer.validated_data).pop("valid_for", 3)

        try:
            serializer.save(
                accessible_projects=accessible_projects,
                token=secrets.token_hex(16),
                expires_at=timezone.now() + timedelta(days=valid_for),
                workspace=self.request.workspace,  # type: ignore
            )
        except IntegrityError:
            raise ResourceConflict(
                detail=(
                    "A pending invitation already exists for this user. "
                    "Update or cancel it before sending a new one."
                )
            )

    @extend_schema(
        operation_id="inviteUser",
        summary="Generate an invitation link for a new user in a workspace",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
