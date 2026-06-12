from rest_framework import serializers

from .models import License


class LicenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = License
        fields = [
            "installed_at",
            "installed_by",
            "is_valid",
            "expires_at",
        ]


class LicenseInstallRequestSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()


class LicenseInstallRemoteResponseSerializer(serializers.Serializer):
    key = serializers.CharField()
