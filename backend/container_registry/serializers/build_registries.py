from typing import Optional
from rest_framework import serializers

from ..models import BuildRegistry, ContainerRegistryCredentials
from .credentials import ContainerRegistryListCreateCredentialsSerializer
import django_filters
from temporal.workflows import DeployBuildRegistryWorkflow
from temporal.client import TemporalClient
from temporal.shared import RegistryConfig, RegistryDetails
from django.db import transaction


class BuildRegistryFilterSet(django_filters.FilterSet):
    class Meta:
        model = BuildRegistry
        fields = ["is_managed"]


class BuildRegistryListCreateSerializer(serializers.ModelSerializer):
    external_credentials = ContainerRegistryListCreateCredentialsSerializer(
        read_only=True, allow_null=True
    )
    external_credentials_id = serializers.PrimaryKeyRelatedField(
        queryset=ContainerRegistryCredentials.objects.filter(
            registry_type=ContainerRegistryCredentials.RegistryType.GENERIC
        ),
        write_only=True,
        required=False,
    )

    def validate(self, attrs: dict):
        managed = attrs.get("is_managed", True)
        external = attrs.get("external_credentials_id")

        if not managed and external is None:
            raise serializers.ValidationError(
                {
                    "external_credentials_id": [
                        "You must provide external credentials when creating an unmanaged registry"
                    ]
                }
            )

        if managed:
            attrs.pop("external_credentials_id", None)

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        external_credentials: ContainerRegistryCredentials | None = validated_data.pop(
            "external_credentials_id", None
        )

        registry = BuildRegistry.objects.create(
            external_credentials=external_credentials,
            **validated_data,
        )

        if registry.is_managed:

            def commit_callback():
                # TODO: s3

                config = RegistryConfig(
                    storage=RegistryConfig.StorageConfig(
                        filesystem=RegistryConfig.StorageConfig.FilesystemDriver()
                        if registry.storage_backend
                        == BuildRegistry.StorageBackend.LOCAL
                        else None
                    )
                )
                payload = RegistryDetails(
                    service_alias=registry.service_alias,
                    config=config,
                    swarm_service_name=registry.swarm_service_name,
                    name=registry.name,
                    id=registry.id,
                )

                TemporalClient.start_workflow(
                    workflow=DeployBuildRegistryWorkflow.run,
                    arg=payload,
                    id=registry.workflow_id,
                )

            transaction.on_commit(commit_callback)

        return registry

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_managed",
            "external_credentials",
            "external_credentials_id",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }
