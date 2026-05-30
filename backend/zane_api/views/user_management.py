from typing import cast

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, CreateAPIView, UpdateAPIView

from rest_framework import status

from .base import ResourceConflict


from ..models import Workspace, WorkspaceMembership, WorkspaceRole, WorkspaceInvitation
from rest_framework import exceptions
from ..serializers import WorkspaceInvitationSerializer
from ..permissions import (
    HasWorkspace,
    IsWorkspaceAdmin,
)
import secrets
from django.db.models import QuerySet
from django.utils import timezone
from datetime import timedelta


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

    def get_serializer(self, *args, **kwargs):
        return super().get_serializer(*args, **kwargs)

    @extend_schema(
        operation_id="inviteUser",
        summary="Generate an invitation link for a new user in a workspace",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
