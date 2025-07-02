from rest_framework.generics import ListAPIView, DestroyAPIView
from ..serializers import GitAppSerializer, GitAppListPagination
from drf_spectacular.utils import extend_schema

from zane_api.models import GitApp


class DeleteGitAppAPIView(DestroyAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab").all()

    @extend_schema(operation_id="deleteGitApp", summary="Delete a git app")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class ListGitAppsAPIView(ListAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab").all()
    pagination_class = GitAppListPagination

    @extend_schema(operation_id="getGitAppsList", summary="List all git apps")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
