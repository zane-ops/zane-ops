from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from ..serializers import GitAppSerializer
from drf_spectacular.utils import extend_schema

from zane_api.models import GitApp, DeploymentChange
from zane_api.views.base import ResourceConflict
from rest_framework.response import Response
from rest_framework import status


class GitAppDetailsAPIView(RetrieveDestroyAPIView):
    serializer_class = GitAppSerializer
    queryset = GitApp.objects.filter().select_related("github", "gitlab")
    lookup_field = "id"

    def destroy(self, request, *args, **kwargs):
        instance: GitApp = self.get_object()

        changes = DeploymentChange.objects.filter(
            new_value__git_app__id=instance.id,
            field=DeploymentChange.ChangeField.GIT_SOURCE,
        )
        if changes.count() > 0:
            raise ResourceConflict(
                "This Git app cannot be deleted as it is referenced by a service or deployment"
            )

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
