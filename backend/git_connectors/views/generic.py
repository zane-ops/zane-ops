from typing import cast
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.request import Request
from ..serializers import (
    GitAppSerializer,
    GitRepositorySerializer,
    GitRepositoryListFilterSet,
    GitRepositoryListPagination,
)
from drf_spectacular.utils import extend_schema
from django.db.models import QuerySet, Q

from zane_api.models import GitApp, DeploymentChange
from zane_api.views.base import ResourceConflict
from rest_framework.response import Response
from rest_framework import status
from ..models import GitRepository, GitlabApp
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import exceptions


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

    @extend_schema(operation_id="listGitApps", summary="List all git apps")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ListGitRepositoriesAPIView(ListAPIView):
    serializer_class = GitRepositorySerializer
    queryset = (
        GitRepository.objects.filter()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = GitRepositoryListFilterSet

    def get_queryset(self, request: Request) -> QuerySet[GitRepository]:  # type: ignore
        app_id = self.kwargs["id"]
        should_resync_repos = request.query_params.get("resync_repos") == "true"
        try:
            gitapp = (
                GitApp.objects.filter(
                    Q(id=app_id) & (Q(github__isnull=False) | Q(gitlab__isnull=False))
                )
                .select_related("github", "gitlab")
                .get()
            )
        except GitApp.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A Git app with the `{app_id}` does not exist."
            )

        if gitapp.github:
            return gitapp.github.repositories

        gl_app = cast(GitlabApp, gitapp.gitlab)
        if should_resync_repos:
            gl_app.fetch_all_repositories_from_gitlab()
        return gl_app.repositories

    def filter_queryset(self, queryset: QuerySet[GitRepository]):
        queryset = super().filter_queryset(queryset)
        return queryset[:30]

    @extend_schema(
        operation_id="listGitAppRepositories",
        summary="List all repositories for a git app",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ListGitRepositoriesPaginatedAPIView(ListAPIView):
    serializer_class = GitRepositorySerializer
    queryset = (
        GitRepository.objects.filter()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = GitRepositoryListPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = GitRepositoryListFilterSet

    def get_queryset(self) -> QuerySet[GitRepository]:  # type: ignore
        app_id = self.kwargs["id"]
        try:
            gitapp = (
                GitApp.objects.filter(
                    Q(id=app_id) & (Q(github__isnull=False) | Q(gitlab__isnull=False))
                )
                .select_related("github", "gitlab")
                .get()
            )
        except GitApp.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A Git app with the `{app_id}` does not exist."
            )

        if gitapp.github:
            return gitapp.github.repositories

        gl_app = cast(GitlabApp, gitapp.gitlab)
        return gl_app.repositories

    @extend_schema(
        operation_id="listGitAppRepositoriesPaginated",
        summary="List all repositories for a git app (paginated)",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
