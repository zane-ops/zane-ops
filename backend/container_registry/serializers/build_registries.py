import django_filters
import requests
from rest_framework import serializers, status

from ..models import BuildRegistry
from urllib.parse import urlparse
from ..constants import GITHUB_REGISTRY_URL, DOCKER_HUB_REGISTRY_URL
from .credentials import ContainerRegistryListCreateCredentialsSerializer


class BuildRegistryListCreateSerializer(serializers.ModelSerializer):
    external_registry = ContainerRegistryListCreateCredentialsSerializer()

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_managed",
            "is_global",
            "external_registry",
            "storage_backend",
            "service_alias",
        ]
        extra_kwargs = {
            "is_global": {"read_only": True},
        }
