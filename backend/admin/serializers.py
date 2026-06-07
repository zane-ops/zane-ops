from rest_framework import serializers
from django.contrib.auth.models import User
from zane_api.models import Workspace
from zane_api.serializers import WorkspaceMemberSerializer
from .models import PasswordResetToken


class InstanceUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "is_superuser",
        ]


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
