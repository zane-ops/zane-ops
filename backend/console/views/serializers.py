import django_filters
from django.contrib.auth.models import User
from rest_framework import serializers
from zane_api.models import Workspace
from zane_api.views.serializers import DeploymentHttpLogsFilterSet
from django.db.models import QuerySet, Q


class WorkspaceListFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Workspace
        fields = ["name"]


class InstanceUserFilterSet(django_filters.FilterSet):
    query = django_filters.CharFilter(method="filter_query")

    def filter_query(self, qs: QuerySet, name: str, value: str):
        return qs.filter(Q(username__icontains=value) | Q(first_name__icontains=value))

    class Meta:
        model = User
        fields = ["query", "is_active"]


class ProxyHttpLogsFilterSet(DeploymentHttpLogsFilterSet):
    """
    Same filters as for a single service, plus `source`,
    since here logs are not scoped to a service, a stack or a deployment.
    """

    source = django_filters.BaseInFilter(method="filter_multiple_values")

    class Meta(DeploymentHttpLogsFilterSet.Meta):
        fields = DeploymentHttpLogsFilterSet.Meta.fields + ["source"]


class ProxyHttpLogFieldsQuerySerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        choices=[
            "request_host",
            "request_path",
            "request_user_agent",
            "request_ip",
        ]
    )
    value = serializers.CharField(allow_blank=True)
