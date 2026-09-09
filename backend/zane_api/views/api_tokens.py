from typing import cast

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status, serializers
from rest_framework.generics import RetrieveUpdateAPIView, ListCreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.db.models import Q, QuerySet
from ..models import WorkspaceApiToken, WorkspaceRole
from ..permissions import (
    HasRequiredScopes,
    HasWorkspace,
    IsWorkspaceMember,
    IsWorkspaceViewer,
    request_access,
)
from ..serializers import (
    WorkspaceApiTokenSerializer,
    WorkspaceApiTokenWithSecretSerializer,
)
from .serializers import (
    CreateWorkspaceApiTokenRequestSerializer,
    WorkspaceApiTokenFilterSet,
)


def _get_token_or_404(request: Request, token_id: str) -> WorkspaceApiToken:
    qs = Q(
        pk=token_id,
        workspace=request.workspace,  # type: ignore
    )

    actor_role = request_access(request).role

    # Admin can see all the other tokens
    # except from the owner and other admins
    if actor_role == WorkspaceRole.ADMIN:
        qs &= Q(role__lt=actor_role) | Q(created_by=request.user)
    elif actor_role == WorkspaceRole.OWNER:
        # Owners can see all the tokens
        pass
    else:
        # For the other users, they can only see their own tokens
        qs &= Q(created_by=request.user)

    try:
        token = (
            WorkspaceApiToken.objects.filter(qs)
            .select_related("created_by", "workspace")
            .prefetch_related("accessible_projects")
            .get()
        )
    except WorkspaceApiToken.DoesNotExist:
        raise exceptions.NotFound(
            f"An API token with an id of `{token_id}` does not exist in this workspace."
        )
    return token


class WorkspaceApiTokenListCreateAPIView(ListCreateAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    # no `required_scopes` => `HasRequiredScopes` denies API tokens outright:
    # a token can never create or list tokens (plan §10).
    permission_classes = [HasWorkspace, HasRequiredScopes, IsWorkspaceMember]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WorkspaceApiTokenFilterSet
    pagination_class = None

    queryset = WorkspaceApiToken.objects.all()  # just used for the openAPI docs

    def get_serializer_class(self):  # type: ignore
        if self.request.method == "POST":
            return CreateWorkspaceApiTokenRequestSerializer
        return WorkspaceApiTokenSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.request.workspace  # type: ignore
        context["actor_role"] = request_access(self.request).role  # type: ignore
        return context

    def get_serializer(self, *args, **kwargs) -> serializers.Serializer:  # type: ignore
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self) -> QuerySet[WorkspaceApiToken]:  # type: ignore
        qs = Q(
            workspace=self.request.workspace,  # type: ignore
        )

        actor_role = request_access(self.request).role  # type: ignore

        # Admin can see all the other tokens
        # except from the owner and other admins
        if actor_role == WorkspaceRole.ADMIN:
            qs &= Q(role__lt=actor_role) | Q(created_by=self.request.user)
        elif actor_role == WorkspaceRole.OWNER:
            # Owners can see all the tokens
            pass
        else:
            # For the other users, they can only see their own tokens
            qs &= Q(created_by=self.request.user)

        # your own tokens; Admin and above see every token in the workspace (§9)
        return (
            WorkspaceApiToken.objects.filter(
                qs  # type: ignore
            )
            .select_related("created_by", "workspace")
            .prefetch_related("accessible_projects")
        )

    @extend_schema(
        responses=WorkspaceApiTokenSerializer(many=True),
        operation_id="listWorkspaceApiTokens",
        summary="List API tokens",
    )
    def get(self, request: Request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @transaction.atomic()
    @extend_schema(
        request=CreateWorkspaceApiTokenRequestSerializer,
        responses={201: WorkspaceApiTokenWithSecretSerializer},
        operation_id="createWorkspaceApiToken",
        summary="Create an API token (returns the secret once)",
    )
    def post(self, request: Request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request: Request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = cast(dict, serializer.validated_data)

        token, token_str = WorkspaceApiToken.generate(
            workspace=request.workspace,  # type: ignore
            created_by=request.user,
            name=data["name"],
            role=data["role"],
            scopes=data["scopes"],
            expires_at=data["expires_at"],
        )
        token.accessible_projects.set(data["accessible_project_ids"])

        token.token = token_str  # type: ignore - transient, for the serializer
        output_serializer = WorkspaceApiTokenWithSecretSerializer(token)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceApiTokenDetailAPIView(RetrieveUpdateAPIView):
    permission_classes = [HasWorkspace, HasRequiredScopes, IsWorkspaceViewer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"
    serializer_class = WorkspaceApiTokenSerializer
    http_method_names = ["get", "patch"]

    def get_object(self) -> WorkspaceApiToken:  # type: ignore
        token_id = self.kwargs["token_id"]
        return _get_token_or_404(
            self.request,  # type: ignore
            token_id,
        )

    def perform_update(self, serializer: WorkspaceApiTokenSerializer):
        return super().perform_update(serializer)


class WorkspaceApiTokenRevokeAPIView(APIView):
    permission_classes = [HasWorkspace, HasRequiredScopes, IsWorkspaceMember]
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
