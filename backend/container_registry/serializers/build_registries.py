from typing import cast
from rest_framework import serializers

from ..models import BuildRegistry
import django_filters
from temporal.workflows import DeployBuildRegistryWorkflow
from temporal.client import TemporalClient
from temporal.shared import RegistryConfig, DeployRegistryPayload
from django.db import transaction
import secrets
from django.db.models import Q, F, Value
from zane_api.validators import validate_url_domain


class BuildRegistryFilterSet(django_filters.FilterSet):
    class Meta:
        model = BuildRegistry
        fields = ["is_managed"]


class BuildRegistryListCreateSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(required=True)

    registry_domain = serializers.CharField(validators=[validate_url_domain])
    registry_password = serializers.CharField(write_only=True, required=False)

    def validate_is_global(self, is_global: bool):
        if not is_global and not BuildRegistry.objects.filter(is_global=True).exists():
            raise serializers.ValidationError(
                "At least one global build registry is required."
            )
        return is_global

    def validate(self, attrs: dict):
        managed = attrs.get("is_managed", True)
        password = attrs.get("registry_password")

        if managed:
            attrs.pop("external_credentials_id", None)

            if password is None:
                attrs["registry_password"] = secrets.token_hex()

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        is_global = validated_data.get("is_global")

        if is_global:
            BuildRegistry.objects.update(is_global=False)

        registry = BuildRegistry.objects.create(**validated_data)

        if registry.is_managed:
            registry.service_alias = BuildRegistry.generate_default_service_alias(
                registry
            )
            registry.swarm_service_name = BuildRegistry.generate_default_service_alias(
                registry
            )
            registry.save()

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
                    service_alias=cast(str, registry.service_alias),
                    config=config,
                    swarm_service_name=cast(str, registry.swarm_service_name),
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
            "service_alias",
            "registry_password",
            "version",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "version": {"read_only": True},
            "service_alias": {"read_only": True},
        }


class BuildRegistryUpdateDetailsSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(required=True)

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

    @transaction.atomic()
    def update(self, instance: BuildRegistry, validated_data: dict):
        registry_domain = validated_data.get(
            "registry_domain", instance.registry_domain
        )
        registry_username = validated_data.get(
            "registry_username", instance.registry_username
        )
        registry_password = validated_data.get(
            "registry_password", instance.registry_password
        )
        registry_password = validated_data.get(
            "registry_password", instance.registry_password
        )
        name = validated_data.get("name", instance.name)
        is_global = validated_data.get("is_global", instance.is_global)

        if is_global:
            BuildRegistry.objects.exclude(id=instance.id).update(is_global=False)

        BuildRegistry.objects.filter(pk=instance.id).update(
            registry_domain=registry_domain,
            name=name,
            is_global=is_global,
            registry_username=registry_username,
            registry_password=registry_password,
            version=F("version") + Value(1),
        )

        instance.refresh_from_db()
        return instance

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_managed",
            "is_global",
            "registry_domain",
            "service_alias",
            "registry_username",
            "registry_password",
            "version",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "is_managed": {"read_only": True},
            "version": {"read_only": True},
            "service_alias": {"read_only": True},
            "registry_password": {"write_only": True},
        }
