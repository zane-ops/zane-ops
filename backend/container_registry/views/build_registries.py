import re
from typing import cast
from urllib.parse import unquote
import requests
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView


from ..serializers import (
    BuildRegistryListCreateSerializer,
    BuildRegistryUpdateDetailsSerializer,
    BuildRegistryListPagination,
    BuildRegistryResponseSerializer,
    BuildRegistryQuerySerializer,
)
from ..models import BuildRegistry
from drf_spectacular.utils import extend_schema
from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from zane_api.views import ErrorResponse409Serializer, ResourceConflict
from temporal.workflows import DestroyBuildRegistryWorkflow
from temporal.shared import DeleteSwarmRegistryServiceDetails
from temporal.client import TemporalClient
from rest_framework.views import APIView
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import exceptions, status
from zane_api.views.base import BadRequest


class BuildRegistryListCreateAPIView(ListCreateAPIView):
    serializer_class = BuildRegistryListCreateSerializer
    queryset = BuildRegistry.objects.all()
    pagination_class = BuildRegistryListPagination

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
        if registry.is_default:
            raise ResourceConflict("Cannot delete the global registry.")

        url = registry.registry_domain
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


class BuildRegistryListImagesAPIView(APIView):
    @extend_schema(
        parameters=[BuildRegistryQuerySerializer],
        responses={200: BuildRegistryResponseSerializer},
        operation_id="listRegistryImages",
        summary="List images in registry",
    )
    def get(self, request: Request, id: str):
        try:
            registry = BuildRegistry.objects.get(pk=id)
        except BuildRegistry.DoesNotExist:
            raise exceptions.NotFound(
                f"A build registry with the id `{id}` does not exist."
            )

        form = BuildRegistryQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        per_page = cast(int, data["per_page"])

        scheme = "https" if registry.is_secure else "http"
        try:
            response = requests.get(
                f"{scheme}://{registry.registry_domain}/v2/_catalog",
                params=dict(
                    n=per_page,
                    last=data.get("cursor"),
                ),
                auth=(registry.registry_username, registry.registry_password),
            )
        except Exception as e:
            raise BadRequest(
                f"Unexpected error when fetching images in registry: `{e}`"
            )
        else:
            if not status.is_success(response.status_code):
                raise BadRequest(
                    f"Unexpected error when fetching images in registry: `{response.text}`"
                )

        # ex value: '</v2/_catalog?last=simple-poke&n=5>; rel="next"'
        link_header = response.headers.get("Link")

        cursor = None
        if link_header:
            value = unquote(link_header.split(";")[0])
            next_link_regex = re.compile(r"<\/v2\/_catalog\?last=(.*)\&n=\d+>$")
            values = next_link_regex.findall(value)
            if len(values) > 0:
                cursor = values[0]

        json = response.json()
        serializer = BuildRegistryResponseSerializer(
            dict(
                results=json["repositories"],
                cursor=cursor,
                per_page=per_page,
            )
        )
        return Response(serializer.data)
