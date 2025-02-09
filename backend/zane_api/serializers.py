import os

from django.contrib.auth.models import User
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from drf_standardized_errors.openapi_serializers import ClientErrorEnum
from rest_framework import serializers
from rest_framework.serializers import *  # type: ignore

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
    errors = Error409Serializer(many=True)  # type: ignore


class URLPathField(CharField):
    default_validators = [validate_url_path]

    def to_internal_value(self, data):
        data = super().to_internal_value(data).strip()
        return os.path.normpath(data)


class URLDomainField(CharField):
    default_validators = [validate_url_domain]


class CustomChoiceField(ChoiceField):
    default_error_messages = {"invalid_choice": _("Please choose a valid option.")}


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
        fields = ["id", "slug", "archived_at", "description"]


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


class ConfigSerializer(ModelSerializer):
    class Meta:
        model = models.Config
        fields = [
            "id",
            "name",
            "mount_path",
            "contents",
            "language",
            "version",
        ]


class URLRedirectModelSerializer(serializers.Serializer):
    url = serializers.URLField()
    permanent = serializers.BooleanField(default=False)


class URLModelSerializer(ModelSerializer):
    redirect_to = URLRedirectModelSerializer(allow_null=True)

    class Meta:
        model = models.URL
        fields = [
            "id",
            "domain",
            "base_path",
            "strip_prefix",
            "redirect_to",
            "associated_port",
        ]


class DockerEnvVariableSerializer(ModelSerializer):
    class Meta:
        model = models.DockerEnvVariable
        fields = ["id", "key", "value"]


class PortConfigurationSerializer(ModelSerializer):
    class Meta:
        model = models.PortConfiguration
        fields = ["id", "host", "forwarded"]

    def to_representation(self, instance: models.PortConfiguration):
        ret = super().to_representation(instance)
        # in the database `host` is stored as null for HTTP hosts, but the user should only
        # see it as `80`
        if ret.get("host") is None:
            ret["host"] = 80
        return ret


class HealthCheckSerializer(ModelSerializer):
    class Meta:
        model = models.HealthCheck
        fields = [
            "id",
            "type",
            "value",
            "timeout_seconds",
            "interval_seconds",
            "associated_port",
        ]


class DockerDeploymentChangeSerializer(ModelSerializer):
    class Meta:
        model = models.DockerDeploymentChange
        fields = [
            "id",
            "type",
            "field",
            "new_value",
            "old_value",
            "item_id",
        ]


class DockerCredentialSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)


class MemoryLimitSerializer(serializers.Serializer):
    MEMORY_UNITS = (
        ("BYTES", _("bytes")),
        ("KILOBYTES", _("kilobytes")),
        ("MEGABYTES", _("megabytes")),
        ("GIGABYTES", _("gigabytes")),
    )
    value = serializers.IntegerField(min_value=0, required=True)
    unit = serializers.ChoiceField(choices=MEMORY_UNITS, required=True)


class ResourceLimitsSerializer(serializers.Serializer):
    cpus = serializers.FloatField(required=True, allow_null=True)
    memory = MemoryLimitSerializer(required=True, allow_null=True)


class SystemEnvVariablesSerializer(serializers.Serializer):
    key = serializers.CharField(allow_null=False)
    value = serializers.CharField(allow_null=False)
    comment = serializers.CharField(allow_null=False)


class DockerServiceSerializer(ModelSerializer):
    volumes = VolumeSerializer(read_only=True, many=True)
    configs = ConfigSerializer(read_only=True, many=True)
    urls = URLModelSerializer(read_only=True, many=True)
    ports = PortConfigurationSerializer(read_only=True, many=True)
    env_variables = DockerEnvVariableSerializer(many=True, read_only=True)
    healthcheck = HealthCheckSerializer(read_only=True, allow_null=True)
    network_aliases = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    unapplied_changes = DockerDeploymentChangeSerializer(many=True, read_only=True)
    credentials = DockerCredentialSerializer(allow_null=True)
    resource_limits = ResourceLimitsSerializer(allow_null=True)
    system_env_variables = SystemEnvVariablesSerializer(
        allow_null=False, many=True, default=[]
    )

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
            "project_id",
            "credentials",
            "urls",
            "volumes",
            "deploy_token",
            "ports",
            "env_variables",
            "network_aliases",
            "network_alias",
            "unapplied_changes",
            "resource_limits",
            "system_env_variables",
            "configs",
        ]


class DeploymentDockerSerializer(DockerServiceSerializer):
    image = serializers.CharField(allow_null=False)


class DockerServiceDeploymentURLSerializer(ModelSerializer):
    class Meta:
        model = models.DeploymentURL
        fields = ["domain", "port"]


class DockerServiceDeploymentSerializer(ModelSerializer):
    network_aliases = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    service_snapshot = DeploymentDockerSerializer()
    redeploy_hash = serializers.SerializerMethodField(allow_null=True)
    changes = DockerDeploymentChangeSerializer(many=True, read_only=True)
    urls = DockerServiceDeploymentURLSerializer(many=True, read_only=True)

    @extend_schema_field(OpenApiTypes.STR)
    def get_redeploy_hash(self, obj: models.DockerDeployment):
        return obj.is_redeploy_of.hash if obj.is_redeploy_of is not None else None

    class Meta:
        model = models.DockerDeployment
        fields = [
            "is_current_production",
            "slot",
            "queued_at",
            "started_at",
            "finished_at",
            "redeploy_hash",
            "hash",
            "status",
            "status_reason",
            "urls",
            "network_aliases",
            "unprefixed_hash",
            "service_snapshot",
            "changes",
            "commit_message",
        ]


class HttpLogSerializer(ModelSerializer):
    request_headers = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )
    response_headers = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )

    class Meta:
        model = models.HttpLog
        fields = [
            "id",
            "status",
            "time",
            "deployment_id",
            "service_id",
            "request_id",
            "request_ip",
            "request_path",
            "request_query",
            "request_host",
            "request_protocol",
            "request_method",
            "request_duration_ns",
            "request_headers",
            "response_headers",
            "request_user_agent",
        ]
