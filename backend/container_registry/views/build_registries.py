from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
# from rest_framework.views import APIView
# from rest_framework.request import Request
# from rest_framework.response import Response
# from rest_framework import exceptions, status, serializers

from ..serializers import BuildRegistryListCreateSerializer, BuildRegistryFilterSet
from ..models import BuildRegistry
from drf_spectacular.utils import (
    extend_schema,
    # inline_serializer,
)

# from zane_api.views import ErrorResponse409Serializer, ResourceConflict, BadRequest
from django_filters.rest_framework import DjangoFilterBackend


class BuildRegistryListCreateAPIView(ListCreateAPIView):
    serializer_class = BuildRegistryListCreateSerializer
    queryset = BuildRegistry.objects.all()
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = BuildRegistryFilterSet

    @extend_schema(
        operation_id="getBuildRegistries",
        summary="List all build registries",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
