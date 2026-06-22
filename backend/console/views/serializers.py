import django_filters
from django.contrib.auth.models import User
from zane_api.models import Workspace


class WorkspaceListFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Workspace
        fields = ["name"]


class InstanceUserFilterSet(django_filters.FilterSet):
    username = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = User
        fields = ["username"]
