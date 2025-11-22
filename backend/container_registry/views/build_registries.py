from typing import cast
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView


from ..serializers import (
    BuildRegistryListCreateSerializer,
    BuildRegistryUpdateDetailsSerializer,
    BuildRegistryFilterSet,
)
from ..models import BuildRegistry
from drf_spectacular.utils import extend_schema
from django.db import transaction
from rest_framework.request import Request
from zane_api.views import ErrorResponse409Serializer, ResourceConflict
from django_filters.rest_framework import DjangoFilterBackend
from temporal.workflows import DestroyBuildRegistryWorkflow
from temporal.shared import DeleteSwarmRegistryServiceDetails
from temporal.client import TemporalClient


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
    def get(self, request: Request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BuildRegistryDetailsAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = BuildRegistryUpdateDetailsSerializer
    http_method_names = [
        "get",
        "patch",
        "delete",
    ]
    lookup_url_kwarg = "id"
    queryset = BuildRegistry.objects.all()

    def get_object(self) -> BuildRegistry:  # type: ignore
        return super().get_object()

    @transaction.atomic()
    @extend_schema(
        responses={204: None, 409: ErrorResponse409Serializer},
        operation_id="deleteBuildRegistry",
        summary="Delete build registry",
    )
    def delete(self, request: Request, *args, **kwargs):
        registry = self.get_object()
        if registry.is_global:
            raise ResourceConflict("Cannot delete the global registry.")

        url = registry.registry_domain

        if registry.is_managed:
            swarm_name = cast(str, registry.swarm_service_name)
            service_alias = cast(str, registry.service_alias)

            workflow_id = registry.destroy_workflow_id

            def commit_callback():
                TemporalClient.start_workflow(
                    workflow=DestroyBuildRegistryWorkflow.run,
                    arg=DeleteSwarmRegistryServiceDetails(
                        swarm_service_name=swarm_name,
                        domain=url,
                        service_alias=service_alias,
                    ),
                    id=workflow_id,
                )

            transaction.on_commit(commit_callback)

        return super().delete(request, *args, **kwargs)
