from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from ..serializers import ContainerRegistryCredentialsSerializer
from ..models import ContainerRegistryCredentials
from drf_spectacular.utils import extend_schema
from zane_api.views import (
    ErrorResponse409Serializer,
    ResourceConflict,
)


class ContainerRegistryCredentialsListAPIView(ListCreateAPIView):
    serializer_class = ContainerRegistryCredentialsSerializer
    queryset = ContainerRegistryCredentials.objects.all()
    pagination_class = None

    @extend_schema(
        operation_id="getRegistryCredentials",
        summary="List all container registry credentials",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ContainerRegistryCredentialsDetailsAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = ContainerRegistryCredentialsSerializer
    queryset = ContainerRegistryCredentials.objects.all()
    http_method_names = ["get", "put", "delete"]
    lookup_url_kwarg = "id"

    def get_object(self) -> ContainerRegistryCredentials:  # type: ignore
        return super().get_object()

    @extend_schema(
        responses={409: ErrorResponse409Serializer, 204: None},
        operation_id="deleteRegistryCredentials",
        summary="Delete registry credentials",
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.services.count() > 0:
            raise ResourceConflict(
                "You cannot delete this container registry because it is referenced by at least one service"
            )
        if instance.build_registries.count() > 0:
            raise ResourceConflict(
                "You cannot delete this container registry because it is referenced by at least one build registry"
            )

        return super().destroy(request, *args, **kwargs)
