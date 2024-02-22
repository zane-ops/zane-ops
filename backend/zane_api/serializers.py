from rest_framework import serializers
from django.contrib.auth.models import User


class ErrorResponseSerializer(serializers.Serializer):
    errors = serializers.DictField(required=False)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "is_staff"]


class AuthRouteResponseSerializer(ErrorResponseSerializer):
    user = UserSerializer(read_only=True, many=False)
