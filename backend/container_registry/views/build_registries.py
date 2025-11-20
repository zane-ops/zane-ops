from typing import cast
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView


from ..serializers import (
    BuildRegistryListCreateSerializer,
    BuildRegistryUpdateDetailsSerializer,
    BuildRegistryFilterSet,
    BuildRegistryDeleteSerializer,
)
from ..models import BuildRegistry
from drf_spectacular.utils import extend_schema
from django.db import transaction
from rest_framework.utils.serializer_helpers import ReturnDict


from zane_api.views import ErrorResponse409Serializer, ResourceConflict
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


class BuildRegistryDetailsAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = BuildRegistryUpdateDetailsSerializer
    http_method_names = ["get", "put", "delete"]
    lookup_url_kwarg = "id"

    def get_object(self) -> BuildRegistry:  # type: ignore
        return super().get_object()

    @transaction.atomic()
    @extend_schema(
        request=BuildRegistryDeleteSerializer,
        responses={204: None, 409: ErrorResponse409Serializer},
        operation_id="deleteBuildRegistry",
        summary="Delete build registry",
    )
    def delete(self, request, *args, **kwargs):
        form = BuildRegistryDeleteSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        instance = self.get_object()
        if instance.is_global:
            raise ResourceConflict("Cannot delete the global registry.")

        if data["delete_associated_registry"]:
            # TODO: start the workflow for deleting registries
            pass
        return super().delete(request, *args, **kwargs)
