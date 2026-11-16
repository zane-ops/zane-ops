import re
from typing import cast
from urllib.parse import unquote
import requests
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView


from ..serializers import (
    BuildRegistryListCreateSerializer,
    BuildRegistrySerializer,
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

from zane_api.permissions import IsInstanceOwner


class BuildRegistryListCreateAPIView(ListCreateAPIView):
    serializer_class = BuildRegistryListCreateSerializer
    queryset = BuildRegistry.objects.all()
    pagination_class = BuildRegistryListPagination

    permission_classes = [IsInstanceOwner]

    @extend_schema(
        operation_id="getBuildRegistries",
        summary="List all build registries",
    )
    def get(self, request: Request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BuildRegistryDetailsAPIView(APIView):
    serializer_class = BuildRegistrySerializer
    permission_classes = [IsInstanceOwner]

    def get_object(self) -> BuildRegistry:
        registry = BuildRegistry.get()
        if registry is None:
            raise exceptions.NotFound(f"This instance does not have a build registry.")
        return registry

    @transaction.atomic()
    @extend_schema(
        operation_id="getBuildRegistry",
        summary="get instance build registry",
    )
    def get(self, request: Request):
        registry = self.get_object()
        serializer = BuildRegistrySerializer(registry)
        return Response(serializer.data)

    @transaction.atomic()
    @extend_schema(
        responses={200: BuildRegistrySerializer, 409: ErrorResponse409Serializer},
        operation_id="updateBuildRegistry",
        summary="Update the instance build registry",
    )
    def patch(self, request: Request, *args, **kwargs):
        registry = self.get_object()

        serializer = BuildRegistrySerializer()

        registry_domain = validated_data.get(
            "registry_domain", registry.registry_domain
        )
        registry_username = validated_data.get(
            "registry_username", registry.registry_username
        )
        registry_password = validated_data.get(
            "registry_password", registry.registry_password
        )
        storage_backend = validated_data.get(
            "storage_backend", registry.storage_backend
        )
        s3_credentials = validated_data.get("s3_credentials", registry.s3_credentials)

        name = validated_data.get("name", registry.name)

        BuildRegistry.objects.filter(pk=registry.id).update(
            version=F("version") + Value(1),
            registry_domain=registry_domain,
            name=name,
            registry_username=registry_username,
            registry_password=registry_password,
            storage_backend=storage_backend,
            s3_credentials=s3_credentials,
        )

        def get_storage_config(storage_backend: str, s3_credentials: dict | None):
            fs_config = None
            if storage_backend == BuildRegistry.StorageBackend.LOCAL:
                fs_config = RegistryConfig.StorageConfig.Filesystem()

            s3_config = None
            if (
                storage_backend == BuildRegistry.StorageBackend.S3
                and s3_credentials is not None
            ):
                s3_config = RegistryConfig.StorageConfig.S3(
                    bucket=s3_credentials["bucket"],
                    accesskey=s3_credentials["access_key"],
                    secretkey=s3_credentials["secret_key"],
                    region=s3_credentials["region"],
                    regionendpoint=s3_credentials["endpoint"],
                )
            return RegistryConfig.StorageConfig(filesystem=fs_config, s3=s3_config)

        previous_snapshot = RegistrySnaphot(
            service_alias=cast(str, registry.service_alias),
            swarm_service_name=cast(str, registry.swarm_service_name),
            id=registry.id,
            config=RegistryConfig(
                storage=get_storage_config(
                    registry.storage_backend,
                    registry.s3_credentials,
                )
            ),
            name=registry.name,
            domain=registry.registry_domain,
            username=registry.registry_username,
            password=registry.registry_password,
            version=registry.version,
            monitor_schedule_id=registry.monitor_schedule_id,
            login_refresh_schedule_id=registry.refresh_login_schedule_id,
        )
        new_snapshot = RegistrySnaphot(
            service_alias=cast(str, registry.service_alias),
            swarm_service_name=cast(str, registry.swarm_service_name),
            id=registry.id,
            config=RegistryConfig(
                storage=get_storage_config(
                    storage_backend,
                    s3_credentials,
                )
            ),
            name=name,
            domain=registry_domain,
            username=registry_username,
            password=registry_password,
            version=registry.version + 1,
            monitor_schedule_id=registry.monitor_schedule_id,
            login_refresh_schedule_id=registry.refresh_login_schedule_id,
        )

        def commit_callback():
            payload = UpdateRegistryPayload(
                service_alias=cast(str, registry.service_alias),
                swarm_service_name=cast(str, registry.swarm_service_name),
                id=registry.id,
                previous=previous_snapshot,
                current=new_snapshot,
            )

            TemporalClient.start_workflow(
                workflow=UpdateBuildRegistryWorkflow.run,
                arg=payload,
                id=registry.workflow_id,
            )

        transaction.on_commit(commit_callback)
        registry.refresh_from_db()
        return Response(data={})

    @transaction.atomic()
    @extend_schema(
        responses={204: None, 409: ErrorResponse409Serializer},
        operation_id="deleteBuildRegistry",
        summary="Delete build registry",
    )
    def delete(self, request: Request, *args, **kwargs):
        registry = self.get_object()
        url = registry.registry_domain
        swarm_name = cast(str, registry.swarm_service_name)
        service_alias = cast(str, registry.service_alias)
        delete_workflow_id = registry.destroy_workflow_id
        monitor_workflow_id = registry.monitor_schedule_id

        def commit_callback():
            TemporalClient.start_workflow(
                workflow=DestroyBuildRegistryWorkflow.run,
                arg=DeleteSwarmRegistryServiceDetails(
                    swarm_service_name=swarm_name,
                    domain=url,
                    service_alias=service_alias,
                    monitor_schedule_id=monitor_workflow_id,
                ),
                id=delete_workflow_id,
            )

        transaction.on_commit(commit_callback)

        return super().delete(request, *args, **kwargs)


class BuildRegistryListImagesAPIView(APIView):
    permission_classes = [IsInstanceOwner]

    @extend_schema(
        parameters=[BuildRegistryQuerySerializer],
        responses={200: BuildRegistryResponseSerializer},
        operation_id="listRegistryImages",
        summary="List images in registry",
    )
    def get(self, request: Request):
        registry = BuildRegistry.get()
        if registry is None:
            raise exceptions.NotFound(f"This instance does not have a build registry.")

        form = BuildRegistryQuerySerializer(data=request.query_params)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)

        per_page = cast(int, data["per_page"])

        try:
            response = requests.get(
                f"https://{registry.registry_domain}/v2/_catalog",
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
