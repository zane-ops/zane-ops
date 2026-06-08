import django_filters
from rest_framework import pagination
from django.contrib.auth.models import User
from zane_api.models import Workspace
from rest_framework import serializers


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
