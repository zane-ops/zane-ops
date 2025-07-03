from rest_framework.generics import (
    ListAPIView,
    DestroyAPIView,
)
from ..serializers import GitAppSerializer, GitAppListPagination
from drf_spectacular.utils import extend_schema

from zane_api.models import GitApp


class DeleteGitAppAPIView(DestroyAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab").all()
    lookup_field = "id"

    def destroy(self, request, *args, **kwargs):
        instance: GitApp = self.get_object()
        if instance.github is not None:
            instance.github.delete()
        if instance.gitlab is not None:
            instance.gitlab.delete()
        return super().destroy(request, *args, **kwargs)


class ListGitAppsAPIView(ListAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab").all()
    pagination_class = GitAppListPagination

    @extend_schema(operation_id="getGitAppsList", summary="List all git apps")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
