import os

from django.contrib.auth.models import User
from django.db.models import TextChoices
from drf_standardized_errors.openapi_serializers import ClientErrorEnum
from rest_framework import serializers
from rest_framework.serializers import *

from . import models
from .validators import validate_url_path, validate_url_domain


class ErrorCode409Enum(TextChoices):
    RESOURCE_CONFLICT = "resource_conflict"


class Error409Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode409Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse409Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error409Serializer(many=True)


class URLPathField(CharField):
    default_validators = [validate_url_path]

    def to_internal_value(self, data):
        data = super().to_internal_value(data).strip()
        return os.path.normpath(data)


class URLDomainField(CharField):
    default_validators = [validate_url_domain]


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]


class ProjectSerializer(ModelSerializer):
    healthy_services = serializers.IntegerField(read_only=True)
    total_services = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Project
        fields = [
            "description",
            "id",
            "slug",
            "created_at",
            "updated_at",
            "healthy_services",
            "total_services",
        ]


class ArchivedProjectSerializer(ModelSerializer):
    class Meta:
        model = models.ArchivedProject
        fields = ["slug", "archived_at"]


class VolumeSerializer(ModelSerializer):
    class Meta:
        model = models.Volume
        fields = [
            "id",
            "name",
            "container_path",
            "host_path",
            "mode",
        ]


class URLModelSerializer(ModelSerializer):
    class Meta:
        model = models.URL
        fields = ["id", "domain", "base_path", "strip_prefix"]


class DockerEnvVariableSerializer(ModelSerializer):
    class Meta:
        model = models.DockerEnvVariable
        fields = ["id", "key", "value"]


class PortConfigurationSerializer(ModelSerializer):
    class Meta:
        model = models.PortConfiguration
        fields = ["id", "host", "forwarded"]


class HealthCheckSerializer(ModelSerializer):
    class Meta:
        model = models.HealthCheck
        fields = ["id", "type", "value", "timeout_seconds", "interval_seconds"]


class DockerDeploymentChangeSerializer(ModelSerializer):
    class Meta:
        model = models.DockerDeploymentChange
        fields = ["id", "type", "field", "new_value", "old_value"]


class DockerCredentialSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)


class DockerServiceSerializer(ModelSerializer):
    volumes = VolumeSerializer(read_only=True, many=True)
    urls = URLModelSerializer(read_only=True, many=True)
    ports = PortConfigurationSerializer(read_only=True, many=True)
    env_variables = DockerEnvVariableSerializer(many=True, read_only=True)
    healthcheck = HealthCheckSerializer(read_only=True)
    network_aliases = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    unapplied_changes = DockerDeploymentChangeSerializer(many=True, read_only=True)

    class Meta:
        model = models.DockerRegistryService
        fields = [
            "created_at",
            "updated_at",
            "id",
            "slug",
            "image",
            "command",
            "healthcheck",
            "credentials",
            "urls",
            "volumes",
            "ports",
            "env_variables",
            "network_aliases",
            "unapplied_changes",
        ]


class DockerServiceDeploymentSerializer(ModelSerializer):
    network_aliases = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )

    class Meta:
        model = models.DockerDeployment
        fields = [
            "is_current_production",
            "created_at",
            "is_redeploy_of",
            "hash",
            "status",
            "status_reason",
            "url",
            "network_aliases",
            "service_snapshot",
        ]
