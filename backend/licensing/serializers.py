from rest_framework import serializers
from .models import License
from zane_api.serializers import UserSerializer


class LicenseSerializer(serializers.ModelSerializer):
    installed_by = UserSerializer(read_only=True)

    class Meta:
        model = License
        fields = [
            "installed_at",
            "installed_by",
            "is_valid",
            "expires_at",
            "tier",
        ]


class LicenseInstallRequestSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()


class LicenseInstallRemoteResponseSerializer(serializers.Serializer):
    key = serializers.CharField()
