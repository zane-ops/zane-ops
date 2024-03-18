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


class ForbiddenResponseSerializer(Serializer):
    detail = CharField()
