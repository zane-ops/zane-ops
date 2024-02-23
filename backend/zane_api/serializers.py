from typing import List
from rest_framework.serializers import *
from django.contrib.auth.models import User


class ErrorResponseSerializer(Serializer):
    errors = DictField()


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "is_staff"]
