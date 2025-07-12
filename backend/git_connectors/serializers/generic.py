from rest_framework import serializers, pagination
from zane_api.models import GitApp
from ..models import GitRepository
import django_filters
from django.db.models import QuerySet

from .github import GithubAppSerializer
from .gitlab import GitlabAppSerializer


class GitAppSerializer(serializers.ModelSerializer):
    github = GithubAppSerializer(allow_null=True)
    gitlab = GitlabAppSerializer(allow_null=True)

    class Meta:
        model = GitApp
        fields = ["id", "github", "gitlab"]


class GitRepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GitRepository
        fields = [
            "id",
            "path",
            "url",
            "private",
        ]


class GitRepositoryListFilterSet(django_filters.FilterSet):
    query = django_filters.CharFilter(method="filter_query")

    def filter_query(self, qs: QuerySet, name: str, value: str):
        return qs.filter(path__icontains=value)

    class Meta:
        model = GitRepository
        fields = ["query"]


class GitRepositoryListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


class GitRepoQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1)
    per_page = serializers.IntegerField(default=30)
