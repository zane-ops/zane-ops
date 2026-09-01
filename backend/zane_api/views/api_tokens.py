from typing import cast

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ..models import WorkspaceApiToken, WorkspaceMembership, WorkspaceRole
from ..permissions import (
    HasRequiredScopes,
    HasWorkspace,
    IsWorkspaceMember,
    IsWorkspaceViewer,
)
from ..serializers import (
    WorkspaceApiTokenSerializer,
    WorkspaceApiTokenWithSecretSerializer,
)
from .serializers import (
    CreateWorkspaceApiTokenRequestSerializer,
    UpdateWorkspaceApiTokenRequestSerializer,
)


def _actor_role(request: Request) -> int:
    membership = WorkspaceMembership.objects.get(
        user=request.user,
        workspace=request.workspace,  # type: ignore
    )
    return membership.role


def _get_token_or_404(request: Request, token_id: str) -> WorkspaceApiToken:
    token = (
        WorkspaceApiToken.objects.filter(
            pk=token_id,
            workspace=request.workspace,  # type: ignore
        )
        .select_related("created_by", "workspace")
        .prefetch_related("accessible_projects")
        .first()
    )

    is_creator = token is not None and token.created_by_id == request.user.id  # type: ignore
    if token is None or (not is_creator and _actor_role(request) < WorkspaceRole.ADMIN):
        raise exceptions.NotFound(
            f"An API token with an id of `{token_id}` does not exist in this workspace."
        )
    return token


class WorkspaceApiTokenListCreateAPIView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    def get_permissions(self):
        # no `required_scopes` => `HasRequiredScopes` denies API tokens outright:
        # a token can never create or list tokens (plan §10).
        if self.request.method == "POST":
            return [HasWorkspace(), HasRequiredScopes(), IsWorkspaceMember()]
        return [HasWorkspace(), HasRequiredScopes(), IsWorkspaceViewer()]

    @extend_schema(
        responses=WorkspaceApiTokenSerializer(many=True),
        operation_id="listWorkspaceApiTokens",
        summary="List API tokens",
    )
    def get(self, request: Request):
        # your own tokens; Admin and above see every token in the workspace (§9)
        tokens = (
            WorkspaceApiToken.objects.filter(
                workspace=request.workspace  # type: ignore
            )
            .select_related("created_by", "workspace")
            .prefetch_related("accessible_projects")
        )
        if _actor_role(request) < WorkspaceRole.ADMIN:
            tokens = tokens.filter(created_by=request.user)

        serializer = WorkspaceApiTokenSerializer(tokens, many=True)
        return Response(serializer.data)

    @transaction.atomic()
    @extend_schema(
        request=CreateWorkspaceApiTokenRequestSerializer,
        responses={201: WorkspaceApiTokenWithSecretSerializer},
        operation_id="createWorkspaceApiToken",
        summary="Create an API token (returns the secret once)",
    )
    def post(self, request: Request):
        form = CreateWorkspaceApiTokenRequestSerializer(
            data=request.data,
            context={
                "workspace": request.workspace,  # type: ignore
                "actor_role": _actor_role(request),
            },
        )
        form.is_valid(raise_exception=True)
        data = cast(dict, form.validated_data)

        token, full_token = WorkspaceApiToken.generate(
            workspace=request.workspace,  # type: ignore
            created_by=request.user,
            name=data["name"],
            role=data["role"],
            scopes=data["scopes"],
            expires_at=data["expires_at"],
        )
        token.accessible_projects.set(data["accessible_project_ids"])

        token.token = full_token  # type: ignore - transient, for the serializer
        serializer = WorkspaceApiTokenWithSecretSerializer(token)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceApiTokenDetailAPIView(APIView):
    permission_classes = [HasWorkspace, HasRequiredScopes, IsWorkspaceViewer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    @extend_schema(
        responses=WorkspaceApiTokenSerializer,
        operation_id="getWorkspaceApiToken",
        summary="Get an API token",
    )
    def get(self, request: Request, token_id: str):
        token = _get_token_or_404(request, token_id)
        return Response(WorkspaceApiTokenSerializer(token).data)

    @extend_schema(
        request=UpdateWorkspaceApiTokenRequestSerializer,
        responses=WorkspaceApiTokenSerializer,
        operation_id="updateWorkspaceApiToken",
        summary="Update an API token",
    )
    def patch(self, request: Request, token_id: str):
        token = _get_token_or_404(request, token_id)

        form = UpdateWorkspaceApiTokenRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(dict, form.validated_data)

        if "name" in data:
            token.name = data["name"]
            token.save(update_fields=["name", "updated_at"])

        return Response(WorkspaceApiTokenSerializer(token).data)


class WorkspaceApiTokenRevokeAPIView(APIView):
    permission_classes = [HasWorkspace, HasRequiredScopes, IsWorkspaceViewer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    @extend_schema(
        request=None,
        responses=WorkspaceApiTokenSerializer,
        operation_id="revokeWorkspaceApiToken",
        summary="Revoke an API token",
    )
    def post(self, request: Request, token_id: str):
        token = _get_token_or_404(request, token_id)
        token.revoke()
        return Response(WorkspaceApiTokenSerializer(token).data)
