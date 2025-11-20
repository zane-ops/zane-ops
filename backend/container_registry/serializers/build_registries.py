from typing import cast
from rest_framework import serializers

from ..models import BuildRegistry, ContainerRegistryCredentials
from .credentials import ContainerRegistryListCreateCredentialsSerializer
import django_filters
from temporal.workflows import DeployBuildRegistryWorkflow
from temporal.client import TemporalClient
from temporal.shared import RegistryConfig, RegistryDetails
from django.db import transaction
import secrets
from django.db.models import Q


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
    is_global = serializers.BooleanField(required=True)
    url = serializers.URLField(write_only=True, required=False)
    username = serializers.SlugField(write_only=True, default="zane")
    password = serializers.CharField(write_only=True, required=False)

    def validate_is_global(self, is_global: bool):
        if not is_global and not BuildRegistry.objects.filter(is_global=True).exists():
            raise serializers.ValidationError(
                "At least one global build registry is required."
            )
        return is_global

    def validate(self, attrs: dict):
        managed = attrs.get("is_managed", True)
        external = attrs.get("external_credentials_id")
        url = attrs.get("url")
        password = attrs.get("password")

        if not managed and external is None:
            raise serializers.ValidationError(
                {
                    "external_credentials_id": [
                        "You must provide external credentials when creating an unmanaged registry"
                    ]
                }
            )

        if managed and url is None:
            raise serializers.ValidationError(
                {"url": ["You must define a URL when creating a managed registry."]}
            )

        if managed:
            attrs.pop("external_credentials_id", None)

            if password is None:
                attrs["password"] = secrets.token_hex()

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        external_credentials: ContainerRegistryCredentials | None = validated_data.pop(
            "external_credentials_id", None
        )
        url = validated_data.pop("url", None)
        username = validated_data.pop("username", None)
        password = validated_data.pop("password", None)

        is_global = validated_data.get("is_global")
        is_managed = validated_data.get("is_managed")

        if is_global:
            BuildRegistry.objects.update(is_global=False)

        if is_managed:
            external_credentials = ContainerRegistryCredentials.objects.create(
                url=url,
                password=password,
                username=username,
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
            "is_global",
            "url",
            "username",
            "password",
            "external_credentials",
            "external_credentials_id",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }


class BuildRegistryUpdateDetailsSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(required=True)

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

    def validate_is_global(self, is_global: bool):
        self.instance = cast(BuildRegistry, self.instance)
        if (
            not is_global
            and not BuildRegistry.objects.filter(
                Q(is_global=True) & ~Q(pk=self.instance.id)
            ).exists()
        ):
            raise serializers.ValidationError(
                "At least one build registry must be set as the global registry."
            )
        return is_global

    def update(self, instance: BuildRegistry, validated_data: dict):
        external_credentials: ContainerRegistryCredentials | None = validated_data.pop(
            "external_credentials_id", None
        )

        if not instance.is_managed:
            instance.external_credentials = external_credentials

        return super().update(instance, validated_data)

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_managed",
            "is_global",
            "external_credentials",
            "external_credentials_id",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "is_managed": {"read_only": True},
        }


class BuildRegistryDeleteSerializer(serializers.Serializer):
    delete_associated_registry = serializers.BooleanField(default=True)
