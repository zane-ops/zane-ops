from rest_framework.generics import (
    ListAPIView,
    DestroyAPIView,
)
from ..serializers import GitAppSerializer
from drf_spectacular.utils import extend_schema

from zane_api.models import GitApp
from rest_framework.response import Response
from rest_framework import status


class DeleteGitAppAPIView(DestroyAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab")
    lookup_field = "id"

    def destroy(self, request, *args, **kwargs):
        instance: GitApp = self.get_object()
        if instance.github is not None:
            instance.github.delete()
        if instance.gitlab is not None:
            instance.gitlab.delete()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListGitAppsAPIView(ListAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab")
    pagination_class = None

    @extend_schema(operation_id="getGitAppsList", summary="List all git apps")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
