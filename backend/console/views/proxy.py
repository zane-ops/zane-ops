from typing import cast

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from zane_api.models import HttpLog
from zane_api.permissions import IsInstanceOwner
from zane_api.serializers import HttpLogSerializer
from zane_api.utils import Colors
from zane_api.views.base import EMPTY_CURSOR_RESPONSE
from zane_api.views.serializers import (
    DeploymentHttpLogsPagination,
    HttpLogFieldsResponseSerializer,
)

from .serializers import ProxyHttpLogFieldsQuerySerializer, ProxyHttpLogsFilterSet


class ProxyHttpLogsAPIView(ListAPIView):
    serializer_class = HttpLogSerializer
    queryset = HttpLog.objects.all()
    pagination_class = DeploymentHttpLogsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProxyHttpLogsFilterSet
    permission_classes = [IsInstanceOwner]

    @extend_schema(
        operation_id="getProxyHttpLogs",
        summary="Get all HTTP logs",
        description="Every request that went through the proxy,"
        " for all the services of the instance and for ZaneOps itself.",
    )
    def get(self, request: Request, *args, **kwargs):
        try:
            print("====== PROXY HTTP LOGS SEARCH ======")
            print(f"Params: {Colors.GREY}{request.query_params}{Colors.ENDC}")
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid cursor" in str(e.detail):
                return Response(EMPTY_CURSOR_RESPONSE)
            raise e


class SingleProxyHttpLogAPIView(RetrieveAPIView):
    serializer_class = HttpLogSerializer
    queryset = HttpLog.objects.all()
    lookup_field = "request_uuid"
    permission_classes = [IsInstanceOwner]


class ProxyHttpLogsFieldsAPIView(APIView):
    serializer_class = HttpLogFieldsResponseSerializer
    permission_classes = [IsInstanceOwner]

    @extend_schema(
        operation_id="getProxyHttpLogsFields",
        summary="Get http logs fields values",
        parameters=[ProxyHttpLogFieldsQuerySerializer],
    )
    def get(self, request: Request):
        form = ProxyHttpLogFieldsQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.data)
        field = data["field"]
        value = data["value"]

        condition = Q()
        if len(value) > 0:
            condition &= Q(**{f"{field}__startswith": value})

        values = (
            HttpLog.objects.filter(condition)
            .order_by(field)
            .values_list(field, flat=True)
            .distinct()[:7]
        )

        serializer = HttpLogFieldsResponseSerializer([item for item in values])
        return Response(serializer.data)
