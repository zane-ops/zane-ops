import os

from django.contrib.auth.models import User
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from drf_standardized_errors.openapi_serializers import ClientErrorEnum
from rest_framework import serializers
from . import models
from .validators import validate_env_name, validate_url_path, validate_url_domain
from git_connectors.serializers import GitAppSerializer, GitRepositorySerializer


class ErrorCode409Enum(TextChoices):
    RESOURCE_CONFLICT = "resource_conflict"


class Error409Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode409Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse409Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error409Serializer(many=True)  # type: ignore


class URLPathField(serializers.CharField):
    default_validators = [validate_url_path]

    def to_internal_value(self, data):
        data = super().to_internal_value(data).strip()
        return os.path.normpath(data)


class URLDomainField(serializers.CharField):
    default_validators = [validate_url_domain]


class CustomChoiceField(serializers.ChoiceField):
    default_error_messages = {"invalid_choice": _("Please choose a valid option.")}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]


class SharedEnvVariableSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    key = serializers.CharField(required=True, validators=[validate_env_name])

    class Meta:
        model = models.SharedEnvVariable
        fields = ["id", "key", "value"]


class SimpleProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = ["id", "slug"]


class SimpleEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Environment
        fields = ["id", "name", "is_preview"]


class SimpleServiceSerializer(serializers.ModelSerializer):
    project = SimpleProjectSerializer(read_only=True)
    environment = SimpleEnvironmentSerializer(read_only=True)

    class Meta:
        model = models.Service
        fields = ["id", "slug", "project", "environment"]


class SimpleDeploymentSerializer(serializers.ModelSerializer):
    service = SimpleServiceSerializer(read_only=True)

    class Meta:
        model = models.Deployment
        fields = [
            "is_current_production",
            "queued_at",
            "started_at",
            "finished_at",
            "hash",
            "status",
            "unprefixed_hash",
            "commit_message",
            "service",
        ]


class SimplePreviewMetadataSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.PreviewEnvMetadata
        fields = [
            "id",
            "auth_enabled",
            "auth_user",
            "auth_password",
        ]


class PreviewMetadataSerializer(serializers.ModelSerializer):
    service = SimpleServiceSerializer(read_only=True)

    class Meta:
        model = models.PreviewEnvMetadata
        fields = [
            "id",
            "auth_enabled",
            "auth_user",
            "auth_password",
            "source_trigger",
            "repository_url",
            "external_url",
            "pr_id",
            "pr_title",
            "branch_name",
            "commit_sha",
            "service",
            "ttl_seconds",
            "auto_teardown",
        ]


class EnvironmentSerializer(serializers.ModelSerializer):
    variables = SharedEnvVariableSerializer(many=True, read_only=True)
    preview_metadata = SimplePreviewMetadataSerializer(read_only=True)

    class Meta:
        model = models.Environment
        fields = ["id", "is_preview", "name", "variables", "preview_metadata"]


class ProjectSerializer(serializers.ModelSerializer):
    healthy_services = serializers.IntegerField(read_only=True)
    total_services = serializers.IntegerField(read_only=True)
    environments = EnvironmentSerializer(many=True, read_only=True)

    class Meta:
        model = models.Project
        fields = [
            "environments",
            "description",
            "id",
            "slug",
            "created_at",
            "updated_at",
            "healthy_services",
            "total_services",
        ]


class ArchivedProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ArchivedProject
        fields = ["id", "slug", "archived_at", "description"]


class VolumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Volume
        fields = [
            "id",
            "name",
            "container_path",
            "host_path",
            "mode",
        ]


class ConfigSerializer(serializers.ModelSerializer):
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


class URLModelSerializer(serializers.ModelSerializer):
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


class EnvVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EnvVariable
        fields = ["id", "key", "value"]


class PortConfigurationSerializer(serializers.ModelSerializer):
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


class HealthCheckSerializer(serializers.ModelSerializer):
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


class DeploymentChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DeploymentChange
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


class DockerfileBuilderOptionsSerializer(serializers.Serializer):
    dockerfile_path = serializers.CharField(required=True)
    build_context_dir = serializers.CharField(required=True)
    build_stage_target = serializers.CharField(required=True, allow_null=True)


class StaticDirectoryBuilderOptionsSerializer(serializers.Serializer):
    publish_directory = serializers.CharField(required=True)
    is_spa = serializers.BooleanField(required=True)
    not_found_page = serializers.CharField(required=True, allow_null=True)
    index_page = serializers.CharField(required=True)
    generated_caddyfile = serializers.CharField(allow_null=True, read_only=True)


class NixpacksBuilderOptionsSerializer(StaticDirectoryBuilderOptionsSerializer):
    build_directory = serializers.CharField(required=True, allow_null=True)
    custom_install_command = serializers.CharField(required=True, allow_null=True)
    custom_build_command = serializers.CharField(required=True, allow_null=True)
    custom_start_command = serializers.CharField(required=True, allow_null=True)
    is_static = serializers.BooleanField(required=True)


class RailpackBuilderOptionsSerializer(NixpacksBuilderOptionsSerializer):
    pass


class ServiceSerializer(serializers.ModelSerializer):
    volumes = VolumeSerializer(read_only=True, many=True)
    configs = ConfigSerializer(read_only=True, many=True)
    urls = URLModelSerializer(read_only=True, many=True)
    ports = PortConfigurationSerializer(read_only=True, many=True)
    env_variables = EnvVariableSerializer(many=True, read_only=True)
    healthcheck = HealthCheckSerializer(read_only=True, allow_null=True)
    network_aliases = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    global_network_alias = serializers.CharField(read_only=True)
    unapplied_changes = DeploymentChangeSerializer(many=True, read_only=True)
    credentials = DockerCredentialSerializer(allow_null=True)
    resource_limits = ResourceLimitsSerializer(allow_null=True)
    system_env_variables = SystemEnvVariablesSerializer(
        allow_null=False, many=True, default=[]
    )
    environment = EnvironmentSerializer(read_only=True)
    dockerfile_builder_options = DockerfileBuilderOptionsSerializer(allow_null=True)
    static_dir_builder_options = StaticDirectoryBuilderOptionsSerializer(
        allow_null=True
    )
    nixpacks_builder_options = NixpacksBuilderOptionsSerializer(allow_null=True)
    railpack_builder_options = RailpackBuilderOptionsSerializer(allow_null=True)
    git_app = GitAppSerializer(allow_null=True)
    git_repository = GitRepositorySerializer(allow_null=True)
    next_git_repository = GitRepositorySerializer(allow_null=True)

    def get_fields(self):
        fields = super().get_fields()
        writable = {
            "slug",
            "auto_deploy_enabled",
            "watch_paths",
            "cleanup_queue_on_auto_deploy",
        }
        for name, field in fields.items():
            if name not in writable:
                field.read_only = True
        return fields

    class Meta:
        model = models.Service
        fields = [
            "created_at",
            "updated_at",
            "id",
            "slug",
            "type",
            "image",
            "command",
            "builder",
            "repository_url",
            "branch_name",
            "commit_sha",
            "dockerfile_builder_options",
            "static_dir_builder_options",
            "nixpacks_builder_options",
            "railpack_builder_options",
            "healthcheck",
            "project_id",
            "environment",
            "credentials",
            "urls",
            "volumes",
            "deploy_token",
            "ports",
            "env_variables",
            "network_aliases",
            "network_alias",
            "global_network_alias",
            "unapplied_changes",
            "resource_limits",
            "system_env_variables",
            "configs",
            "git_app",
            "git_repository",
            "next_git_repository",
            "auto_deploy_enabled",
            "watch_paths",
            "cleanup_queue_on_auto_deploy",
            "pr_preview_envs_enabled",
        ]


class DeploymentDockerSerializer(ServiceSerializer):
    image = serializers.CharField(allow_null=False)


class ServiceDeploymentURLSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DeploymentURL
        fields = ["domain", "port"]


class ServiceDeploymentSerializer(serializers.ModelSerializer):
    network_aliases = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    service_snapshot = DeploymentDockerSerializer()
    redeploy_hash = serializers.SerializerMethodField(allow_null=True)
    changes = DeploymentChangeSerializer(many=True, read_only=True)
    urls = ServiceDeploymentURLSerializer(many=True, read_only=True)

    @extend_schema_field(OpenApiTypes.STR)
    def get_redeploy_hash(self, obj: models.Deployment):
        return obj.is_redeploy_of.hash if obj.is_redeploy_of is not None else None

    class Meta:
        model = models.Deployment
        fields = [
            "is_current_production",
            "slot",
            "queued_at",
            "ignore_build_cache",
            "started_at",
            "finished_at",
            "redeploy_hash",
            "trigger_method",
            "hash",
            "status",
            "status_reason",
            "urls",
            "network_aliases",
            "unprefixed_hash",
            "service_snapshot",
            "changes",
            "commit_message",
            "commit_author_name",
            "commit_sha",
            "build_started_at",
            "build_finished_at",
        ]


class HttpLogSerializer(serializers.ModelSerializer):
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


class EnvironmentWithServicesSerializer(serializers.ModelSerializer):
    preview_metadata = PreviewMetadataSerializer(read_only=True, allow_null=True)
    variables = SharedEnvVariableSerializer(many=True, read_only=True)

    class Meta:
        model = models.Environment
        fields = [
            "id",
            "is_preview",
            "name",
            "preview_metadata",
            "variables",
        ]
