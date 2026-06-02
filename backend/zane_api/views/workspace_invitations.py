from typing import cast

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, DestroyAPIView, RetrieveAPIView
from rest_framework import status, permissions

from .base import ResourceConflict, BadRequest


from ..models import WorkspaceMembership, WorkspaceInvitation
from rest_framework import exceptions
from ..serializers import (
    WorkspaceInvitationSerializer,
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
    WorkspaceAcceptInvitationResponseSerializer,
    WorkspaceRegisterRequestSerializer,
)
from django.contrib.auth.models import User, AbstractUser
from django.contrib.auth import login, authenticate
from django.db import transaction


class ListWorkspaceInvitationAPIView(ListAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceInvitationSerializer

    def get_queryset(self) -> QuerySet[WorkspaceInvitation]:  # type: ignore
        return WorkspaceInvitation.objects.filter(
            workspace=self.request.workspace  # type: ignore
        ).prefetch_related("accessible_projects")


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


class WorkspaceRegisterInvitationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic()
    @extend_schema(
        request=WorkspaceRegisterRequestSerializer,
        responses={201: WorkspaceAcceptInvitationResponseSerializer},
        operation_id="registerUserIntoWorkspace",
        summary="Create user account and register them into workspace",
    )
    def post(self, request: Request, token: str):
        try:
            invitation = (
                WorkspaceInvitation.objects.filter(token=token)
                .select_related("workspace")
                .get()
            )
        except WorkspaceInvitation.DoesNotExist:
            raise exceptions.NotFound(
                f"An invitation with the token `{token}` does not exist."
            )

        if invitation.has_existing_account:
            raise BadRequest(
                "This invitation is for an existing account. Please log in to accept it."
            )

        authed_user: AbstractUser = request.user
        if authed_user.is_authenticated:
            raise BadRequest(
                "You must be logged out to create a new account and accept this invitation."
            )

        form = WorkspaceRegisterRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        user = User.objects.create_user(
            username=invitation.username,
            password=data["password"],
        )  # type: ignore

        membership = WorkspaceMembership.objects.create(
            user=user,
            workspace=invitation.workspace,
            role=invitation.role,
        )

        for project in invitation.accessible_projects.all():
            membership.accessible_projects.add(project)

        login(request, user)  # type: ignore

        invitation.delete()

        serializer = WorkspaceAcceptInvitationResponseSerializer({"success": True})
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceAcceptInvitationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic()
    @extend_schema(
        request=None,
        responses={201: WorkspaceAcceptInvitationResponseSerializer},
        operation_id="acceptInvitation",
        summary="Accept workspace invitation",
    )
    def post(self, request: Request, token: str):
        try:
            invitation = (
                WorkspaceInvitation.objects.filter(
                    token=token,
                    username=request.user.username,
                )
                .select_related("workspace")
                .get()
            )
        except WorkspaceInvitation.DoesNotExist:
            raise exceptions.NotFound(
                f"An invitation with the token `{token}` does not exist."
            )

        membership = WorkspaceMembership.objects.create(
            user=request.user,
            workspace=invitation.workspace,
            role=invitation.role,
        )

        for project in invitation.accessible_projects.all():
            membership.accessible_projects.add(project)

        invitation.delete()

        serializer = WorkspaceAcceptInvitationResponseSerializer({"success": True})
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


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

        if data["username"] == self.request.user.username:
            raise ResourceConflict("You cannot invite yourself to the workspace.")

        if WorkspaceMembership.objects.filter(
            user__username=data["username"],
            workspace=self.request.workspace,  # type: ignore
        ).exists():
            raise ResourceConflict("This user is already a member of the workspace.")

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
