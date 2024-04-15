import os

from django.contrib.auth.models import User
from django.db.models import TextChoices
from drf_standardized_errors.openapi_serializers import ServerErrorEnum
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
    type = serializers.ChoiceField(choices=ServerErrorEnum.choices)
    errors = Error409Serializer(many=True)


class StringListField(ListField):
    child = CharField()


class BaseErrorSerializer(Serializer):
    root = StringListField(required=False)


class BaseErrorResponseSerializer(Serializer):
    errors = BaseErrorSerializer()


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
        fields = ["username", "first_name", "last_name", "is_staff"]


class ProjectSerializer(ModelSerializer):
    class Meta:
        model = models.Project
        fields = ["slug", "created_at", "updated_at"]


class ArchivedProjectSerializer(ModelSerializer):
    class Meta:
        model = models.ArchivedProject
        fields = ["slug", "archived_at"]


class VolumeSerializer(ModelSerializer):
    class Meta:
        model = models.Volume
        fields = ["created_at", "updated_at", "id", "name", "containerPath"]


class URLModelSerializer(ModelSerializer):
    class Meta:
        model = models.URL
        fields = ["domain", "base_path", "strip_prefix"]


class DockerEnvVariableSerializer(ModelSerializer):
    class Meta:
        model = models.DockerEnvVariable
        fields = ["key", "value"]


class PortConfigurationSerializer(ModelSerializer):
    class Meta:
        model = models.PortConfiguration
        fields = ["host", "forwarded"]


class DockerServiceSerializer(ModelSerializer):
    volumes = VolumeSerializer(read_only=True, many=True)
    urls = URLModelSerializer(read_only=True, many=True)
    ports = PortConfigurationSerializer(read_only=True, many=True, source="port_config")
    env_variables = DockerEnvVariableSerializer(many=True)

    class Meta:
        model = models.DockerRegistryService
        fields = [
            "image",
            "slug",
            "urls",
            "created_at",
            "updated_at",
            "volumes",
            "command",
            "ports",
            "env_variables",
        ]


class ForbiddenResponseSerializer(BaseErrorResponseSerializer):
    pass
