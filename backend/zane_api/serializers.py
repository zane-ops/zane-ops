from django.contrib.auth.models import User
from rest_framework.serializers import *

from . import models


class StringListField(ListField):
    child = CharField()


class BaseErrorSerializer(Serializer):
    root = StringListField(required=False)


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
