from rest_framework import serializers

from ..models import BuildRegistry, ContainerRegistryCredentials
from .credentials import ContainerRegistryListCreateCredentialsSerializer
import django_filters


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

        return attrs

    def create(self, validated_data: dict):
        external_credentials: ContainerRegistryCredentials | None = validated_data.pop(
            "external_credentials_id", None
        )

        return BuildRegistry.objects.create(
            external_credentials=external_credentials,
            **validated_data,
        )

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_managed",
            "is_global",
            "external_credentials",
            "external_credentials_id",
            "storage_backend",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }
