from typing import cast

from drf_spectacular.utils import extend_schema

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView

from rest_framework import exceptions
from zane_api.models import Workspace, WorkspaceMembership, WorkspaceRole
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


class WorkspaceDetailAPIView(RetrieveAPIView):
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


class WorkspaceTransferOwnershipAPIView(APIView):
    permission_classes = [IsInstanceOwner]

    @transaction.atomic()
    @extend_schema(
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
