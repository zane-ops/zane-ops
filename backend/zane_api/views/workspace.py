from typing import cast

from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import ListAPIView

from rest_framework import status


from ..models import Workspace, WorkspaceMembership
from ..constants import WORKSPACE_SESSION_KEY
from .serializers import SwitchWorkspaceRequestSerializer
from rest_framework import exceptions
from ..serializers import WorkspaceMembershipSerializer

from django.db.models import QuerySet


class WorkspaceMembershipListAPIView(ListAPIView):
    serializer_class = WorkspaceMembershipSerializer

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return WorkspaceMembership.objects.filter(
            user=self.request.user
        ).select_related("workspace")


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
