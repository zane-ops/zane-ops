from rest_framework.generics import ListAPIView
from ..serializers import GitAppSerializer, GitAppListPagination
from drf_spectacular.utils import extend_schema

from zane_api.models import GitApp


class ListGitAppsAPIView(ListAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab").all()
    pagination_class = GitAppListPagination

    @extend_schema(operation_id="getGitAppsList", summary="List all git apps")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
