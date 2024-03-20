import os

from django.contrib.auth.models import User
from rest_framework.serializers import *

from . import models
from .helpers import validate_url_path, validate_url_domain


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
    owner = UserSerializer(many=False, read_only=True)

    class Meta:
        model = models.Project
        fields = ["name", "slug", "archived", "owner", "created_at", "updated_at"]


class VolumeSerializer(ModelSerializer):
    class Meta:
        model = models.Volume
        fields = ["created_at", "updated_at", "slug", "name", "containerPath"]


class URLModelSerializer(ModelSerializer):
    class Meta:
        model = models.URL
        fields = ["domain", "base_path"]


class EnvVariableSerializer(ModelSerializer):
    class Meta:
        model = models.EnvVariable
        fields = ["key", "value", "is_for_production"]


class PortConfigurationSerializer(ModelSerializer):
    class Meta:
        model = models.PortConfiguration
        fields = ["host", "forwarded"]


class DockerServiceSerializer(ModelSerializer):
    volumes = VolumeSerializer(read_only=True, many=True)
    urls = URLModelSerializer(read_only=True, many=True)
    env_variables = EnvVariableSerializer(read_only=True, many=True)
    ports = PortConfigurationSerializer(read_only=True, many=True, source="port_config")

    class Meta:
        model = models.DockerRegistryService
        fields = ["image", "slug", "urls", "created_at", "updated_at", "volumes", "name", "archived", "command",
                  "env_variables", "ports"]


class ForbiddenResponseSerializer(Serializer):
    detail = CharField()
