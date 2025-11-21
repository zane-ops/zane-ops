from typing import cast
from urllib.parse import urlparse
from rest_framework import serializers

from ..models import BuildRegistry, SharedRegistryCredentials
import django_filters
from temporal.workflows import DeployBuildRegistryWorkflow
from temporal.client import TemporalClient
from temporal.shared import RegistryConfig, DeployRegistryPayload
from django.db import transaction
import secrets
from django.db.models import Q
from zane_api.validators import validate_url_domain


class BuildRegistryFilterSet(django_filters.FilterSet):
    class Meta:
        model = BuildRegistry
        fields = ["is_managed"]


class BuildRegistryListCreateSerializer(serializers.ModelSerializer):
    external_credentials_id = serializers.PrimaryKeyRelatedField(
        queryset=SharedRegistryCredentials.objects.filter(
            registry_type=SharedRegistryCredentials.RegistryType.GENERIC
        ),
        write_only=True,
        required=False,
    )
    is_global = serializers.BooleanField(required=True)

    registry_domain = serializers.CharField(
        required=False, validators=[validate_url_domain]
    )
    registry_username = serializers.SlugField(default="zane")
    registry_password = serializers.CharField(write_only=True, required=False)

    def validate_is_global(self, is_global: bool):
        if not is_global and not BuildRegistry.objects.filter(is_global=True).exists():
            raise serializers.ValidationError(
                "At least one global build registry is required."
            )
        return is_global

    def validate(self, attrs: dict):
        managed = attrs.get("is_managed", True)
        external = attrs.get("external_credentials_id")
        url = attrs.get("registry_domain")
        password = attrs.get("registry_password")

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
                {
                    "registry_domain": [
                        "You must define a URL when creating a managed registry."
                    ]
                }
            )

        if managed:
            attrs.pop("external_credentials_id", None)

            if password is None:
                attrs["registry_password"] = secrets.token_hex()

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        external_credentials: SharedRegistryCredentials | None = validated_data.pop(
            "external_credentials_id", None
        )

        registry_domain = validated_data.pop("registry_domain", None)
        registry_username = validated_data.pop("registry_username", None)
        registry_password = validated_data.pop("registry_password", None)

        is_global = validated_data.get("is_global")
        is_managed = validated_data.get("is_managed")

        if is_global:
            BuildRegistry.objects.update(is_global=False)

        registry = BuildRegistry(**validated_data)
        if is_managed:
            registry.registry_domain = registry_domain
            registry.registry_username = registry_username
            registry.registry_password = registry_password
        elif external_credentials is not None:
            registry.registry_domain = urlparse(external_credentials.url).netloc
            registry.registry_username = external_credentials.username
            registry.registry_password = external_credentials.password

        registry.save()

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
                payload = DeployRegistryPayload(
                    service_alias=registry.service_alias,
                    config=config,
                    swarm_service_name=registry.swarm_service_name,
                    name=registry.name,
                    id=registry.id,
                    registry_domain=registry.registry_domain,
                    registry_username=registry.registry_username,
                    registry_password=registry.registry_password,
                    version=registry.version,
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
            "registry_domain",
            "registry_username",
            "registry_password",
            "external_credentials_id",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }


class BuildRegistryUpdateDetailsSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(required=True)

    external_credentials_id = serializers.PrimaryKeyRelatedField(
        queryset=SharedRegistryCredentials.objects.filter(
            registry_type=SharedRegistryCredentials.RegistryType.GENERIC
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

    # def update(self, instance: BuildRegistry, validated_data: dict):
    #     external_credentials: ContainerRegistryCredentials = validated_data.pop(
    #         "external_credentials_id", None
    #     )

    #     if not instance.is_managed:
    #         instance.external_credentials = external_credentials

    #     return super().update(instance, validated_data)

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_managed",
            "is_global",
            "registry_domain",
            "registry_username",
            "registry_password",
            "external_credentials_id",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "is_managed": {"read_only": True},
        }
