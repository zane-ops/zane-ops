from rest_framework import serializers

from zane_api.models import Workspace
from zane_api.serializers import WorkspaceMemberSerializer
from zane_api.validators import validate_cron_schedule
from .models import PasswordResetToken, SystemSettings
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


class WorkspaceTransferOwnershipSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField()

    def validate_owner_id(self, owner_id: int):
        new_owner = User.objects.filter(pk=owner_id).first()
        if new_owner is None:
            raise serializers.ValidationError(
                f"User with id={owner_id} does not exist."
            )

        if not new_owner.is_active:
            raise serializers.ValidationError(
                "You cannot transfer ownership of this workspace to a suspended user."
            )

        return owner_id


class PasswordResetTokenSerializer(serializers.ModelSerializer):
    user = InstanceUserSerializer(read_only=True)

    class Meta:
        model = PasswordResetToken
        fields = ["id", "value", "expires_at", "user"]


class SystemSettingsSerializer(serializers.ModelSerializer):
    docker_system_prune_cron_schedule = serializers.CharField(
        validators=[validate_cron_schedule]
    )
    app_data_cleanup_cron_schedule = serializers.CharField(
        validators=[validate_cron_schedule]
    )
    docker_build_cache_prune_cron_schedule = serializers.CharField(
        validators=[validate_cron_schedule]
    )

    class Meta:
        model = SystemSettings
        fields = [
            "docker_system_prune_cron_schedule",
            "app_data_cleanup_cron_schedule",
            "docker_build_cache_prune_cron_schedule",
            "http_log_retention_days",
            "build_cache_max_age_days",
            "build_cache_max_use_space_bytes",
            "prune_images",
            "prune_containers",
            "prune_volumes",
            "prune_networks",
        ]
