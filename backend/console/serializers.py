from rest_framework import serializers

from zane_api.models import Workspace
from zane_api.serializers import WorkspaceMemberSerializer
from .models import PasswordResetToken
from django.contrib.auth import get_user_model

User = get_user_model()


class InstanceUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "is_superuser",
            "is_active",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "username": {"read_only": True},
            "first_name": {"read_only": True},
            "last_name": {"read_only": True},
            "is_superuser": {"read_only": True},
        }


class WorkspaceDetailSerializer(serializers.ModelSerializer):
    members = WorkspaceMemberSerializer(
        source="memberships",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Workspace
        fields = ["id", "name", "members"]


class PasswordResetTokenSerializer(serializers.ModelSerializer):
    user = InstanceUserSerializer(read_only=True)

    class Meta:
        model = PasswordResetToken
        fields = ["id", "value", "expires_at", "user"]
