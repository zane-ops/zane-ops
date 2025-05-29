import base64
import json
import re

import django_filters
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter
from rest_framework import pagination
from rest_framework.request import Request

import rest_framework.serializers as serializers
from ...models import (
    HttpLog,
)
from ...utils import Colors

from search.dtos import RuntimeLogLevel


# ==============================
#       Collect Logs           #
# ==============================


class DockerContainerLogSerializer(serializers.Serializer):
    log = serializers.CharField(required=True, allow_blank=True, trim_whitespace=False)
    container_id = serializers.CharField(required=True)
    container_name = serializers.CharField(required=True)
    time = serializers.CharField(required=True)
    tag = serializers.CharField(required=True)
    SOURCES = (
        ("stdout", _("standard ouput")),
        ("stderr", _("standard error")),
    )
    source = serializers.ChoiceField(choices=SOURCES, required=True)


class HTTPServiceRequestSerializer(serializers.Serializer):
    remote_ip = serializers.IPAddressField(required=True)
    client_ip = serializers.IPAddressField(required=True)
    remote_port = serializers.CharField(required=True)
    PROTOCOLS = [
        ("HTTP/1.0", "HTTP/1.0"),
        ("HTTP/1.1", "HTTP/1.1"),
        ("HTTP/2.0", "HTTP/2.0"),
        ("HTTP/3.0", "HTTP/3.0"),
    ]
    REQUEST_METHODS = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("DELETE", "DELETE"),
        ("PATCH", "PATCH"),
        ("OPTIONS", "OPTIONS"),
        ("HEAD", "HEAD"),
    ]
    proto = serializers.ChoiceField(choices=PROTOCOLS, required=True)
    method = serializers.ChoiceField(choices=REQUEST_METHODS, required=True)
    host = serializers.CharField(required=True)
    uri = serializers.CharField(required=True)
    headers = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=True,
    )


class HTTPServiceLogSerializer(serializers.Serializer):
    ts = serializers.FloatField(required=True)
    msg = serializers.CharField(required=True)
    LOG_LEVELS = (
        ("debug", _("debug")),
        ("info", _("info")),
        ("warn", _("warn")),
        ("error", _("error")),
        ("panic", _("panic")),
        ("fatal", _("fatal")),
    )
    level = serializers.ChoiceField(choices=LOG_LEVELS, required=True)

    duration = serializers.FloatField()
    status = serializers.IntegerField(min_value=100)
    resp_headers = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )
    request = HTTPServiceRequestSerializer()
    zane_deployment_upstream = serializers.CharField()
    zane_deployment_green_hash = serializers.CharField(
        allow_null=True, required=False, allow_blank=True
    )
    zane_deployment_blue_hash = serializers.CharField(
        allow_null=True, required=False, allow_blank=True
    )
    zane_service_id = serializers.CharField()
    zane_deployment_id = serializers.CharField(required=False)
    uuid = serializers.CharField(allow_null=True, required=False, allow_blank=True)


class DockerContainerLogsRequestSerializer(serializers.ListSerializer):
    child = DockerContainerLogSerializer()


class DockerContainerLogsResponseSerializer(serializers.Serializer):
    simple_logs_inserted = serializers.IntegerField(min_value=0)
    http_logs_inserted = serializers.IntegerField(min_value=0)


# =======================================
#        Deployment BUILD Logs        #
# =======================================


class DeploymentBuildLogsQuerySerializer(serializers.Serializer):
    cursor = serializers.CharField(required=False)
    per_page = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=50
    )

    def validate_cursor(self, cursor: str):
        try:
            decoded_data = base64.b64decode(cursor, validate=True)
            decoded_string = decoded_data.decode("utf-8")
            serializer = CursorSerializer(data=json.loads(decoded_string))
            serializer.is_valid(raise_exception=True)
        except (serializers.ValidationError, ValueError):
            raise serializers.ValidationError(
                {
                    "cursor": "Invalid cursor format, it should be a base64 encoded string of a JSON object."
                }
            )
        return cursor


# =======================================
#        Deployment runtime Logs        #
# =======================================


class DeploymentRuntimeLogsQuerySerializer(serializers.Serializer):
    time_before = serializers.DateTimeField(required=False)
    time_after = serializers.DateTimeField(required=False)
    query = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    level = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[RuntimeLogLevel.INFO, RuntimeLogLevel.ERROR]
        ),
        required=False,
    )
    per_page = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=50
    )
    cursor = serializers.CharField(required=False)

    def validate_cursor(self, cursor: str):
        try:
            decoded_data = base64.b64decode(cursor, validate=True)
            decoded_string = decoded_data.decode("utf-8")
            serializer = CursorSerializer(data=json.loads(decoded_string))
            serializer.is_valid(raise_exception=True)
        except (serializers.ValidationError, ValueError):
            raise serializers.ValidationError(
                {
                    "cursor": "Invalid cursor format, it should be a base64 encoded string of a JSON object."
                }
            )
        return cursor


class CursorSerializer(serializers.Serializer):
    sort = serializers.ListField(required=True, child=serializers.CharField())
    order = serializers.ChoiceField(choices=["desc", "asc"], required=True)


class DeploymentHttpLogsPagination(pagination.CursorPagination):
    page_size = 50
    page_size_query_param = "per_page"
    ordering = ("-time",)

    def get_ordering(self, request: Request, queryset, view):
        filter = DeploymentHttpLogsFilterSet(
            {"sort_by": ",".join(request.GET.getlist("sort_by"))}
        )

        if filter.is_valid():
            ordering = tuple(
                set(filter.form.cleaned_data.get("sort_by", self.ordering))
            )
            if len(ordering) > 0:
                return ordering  # tuple(set(filter.form.cleaned_data.get("sort_by", self.ordering)))

        return self.ordering


class DeploymentHttpLogsFilterSet(django_filters.FilterSet):
    time = django_filters.DateTimeFromToRangeFilter()
    request_method = django_filters.MultipleChoiceFilter(
        choices=HttpLog.RequestMethod.choices
    )
    sort_by = OrderingFilter(fields=["time", "request_duration_ns"])
    request_query = django_filters.CharFilter(
        field_name="request_query", method="filter_query"
    )
    status = django_filters.BaseInFilter(method="filter_multiple_values")
    request_ip = django_filters.BaseInFilter(method="filter_multiple_values")
    request_user_agent = django_filters.BaseInFilter(method="filter_multiple_values")
    request_host = django_filters.BaseInFilter(
        field_name="request_host", method="filter_multiple_values"
    )
    request_path = django_filters.BaseInFilter(method="filter_multiple_values")

    def filter_multiple_values(self, queryset: QuerySet, name: str, value: str):
        params = self.request.GET.getlist(name)  # type: ignore

        status_prefix_path = r"^\dxx$"

        queries = Q()
        if name == "status":
            for param in params:
                if re.match(status_prefix_path, param):
                    prefix = int(param[0])
                    queries = queries | (
                        Q(status__gte=(prefix * 100), status__lte=(prefix * 100) + 99)
                    )
                elif re.match(r"^\d+$", param):
                    queries = queries | Q(status=int(param))
        else:
            queries = Q(**{f"{name}__in": params})
        print(f"Query: {Colors.GREY}{queries}{Colors.ENDC}")
        return queryset.filter(queries)

    def filter_query(self, queryset: QuerySet, name: str, value: str):
        return queryset.filter(request_query__istartswith=value)

    class Meta:
        model = HttpLog
        fields = [
            "time",
            "request_method",
            "request_path",
            "request_host",
            "request_query",
            "status",
            "request_ip",
            "request_id",
            "request_user_agent",
        ]


# ==============================
#       Http logs fields       #
# ==============================


class HttpLogFieldsQuerySerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        choices=[
            "request_host",
            "request_path",
            "request_user_agent",
            "request_ip",
        ]
    )
    value = serializers.CharField(allow_blank=True)


class HttpLogFieldsResponseSerializer(serializers.ListSerializer):
    child = serializers.CharField()
