from drf_spectacular.utils import extend_schema

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView


from django.contrib.auth.models import User
from rest_framework import exceptions
from zane_api.models import Workspace
from zane_api.permissions import IsInstanceOwner, HasWorkspace
from zane_api.serializers import WorkspaceSerializer

from zane_api.views import EMPTY_PAGINATED_RESPONSE
from .serializers import InstanceUserPagination, WorkspaceListFilterSet, InstanceUserFilterSet
from ..serializers import InstanceUserSerializer


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


class ListInstanceUsersAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = InstanceUserSerializer
    queryset = User.objects.all()
    pagination_class = InstanceUserPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = InstanceUserFilterSet

    @extend_schema(
        summary="List all users in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e


class InstanceUserDetailAPIView(RetrieveAPIView):
    permission_classes = [HasWorkspace, IsInstanceOwner]
    serializer_class = InstanceUserSerializer
    queryset = User.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "id"
