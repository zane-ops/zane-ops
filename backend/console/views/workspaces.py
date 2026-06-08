from drf_spectacular.utils import extend_schema

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView


from rest_framework import exceptions
from zane_api.models import Workspace
from zane_api.permissions import IsInstanceOwner
from zane_api.serializers import WorkspaceSerializer

from zane_api.views import EMPTY_PAGINATED_RESPONSE
from .serializers import InstanceUserPagination, WorkspaceListFilterSet
from ..serializers import WorkspaceDetailSerializer


class ListWorkspacesAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.all()
    pagination_class = InstanceUserPagination
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
