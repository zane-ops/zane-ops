from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from ..serializers import (
    ContainerRegistryListCreateCredentialsSerializer,
    ContainerRegistryCredentialsUpdateDetailsSerializer,
    ContainerRegistryCredentialsFilterSet,
)
from ..models import ContainerRegistryCredentials
from drf_spectacular.utils import extend_schema
from zane_api.views import (
    ErrorResponse409Serializer,
    ResourceConflict,
)
from django_filters.rest_framework import DjangoFilterBackend
from zane_api.models import DeploymentChange


class ContainerRegistryCredentialsListAPIView(ListCreateAPIView):
    serializer_class = ContainerRegistryListCreateCredentialsSerializer
    queryset = ContainerRegistryCredentials.objects.all()
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = ContainerRegistryCredentialsFilterSet

    @extend_schema(
        operation_id="getRegistryCredentials",
        summary="List all container registry credentials",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ContainerRegistryCredentialsDetailsAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = ContainerRegistryCredentialsUpdateDetailsSerializer
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

        changes = DeploymentChange.objects.filter(
            new_value__container_registry_credentials__id=instance.id,
            field=DeploymentChange.ChangeField.SOURCE,
        )
        if changes.count() > 0:
            raise ResourceConflict(
                "You cannot delete this container registry because it is referenced by at least one deployment"
            )

        return super().destroy(request, *args, **kwargs)
