from drf_spectacular.utils import extend_schema

from rest_framework.generics import ListAPIView
from rest_framework import exceptions
from rest_framework.response import Response

from zane_api.permissions import IsInstanceOwner
from zane_api.views.base import DefaultPageNumberPagination, EMPTY_PAGINATED_RESPONSE

from swarm.models import SwarmNode
from swarm.serializers import SwarmNodeSerializer


class SwarmNodeListAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SwarmNodeSerializer
    queryset = SwarmNode.objects.all().order_by("hostname")
    pagination_class = DefaultPageNumberPagination

    @extend_schema(
        summary="List all swarm nodes in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e
