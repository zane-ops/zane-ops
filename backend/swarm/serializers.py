import django_filters
from rest_framework import serializers

from .models import SSHKey, SwarmNode
from .validators import validate_unix_username


class SSHKeyFilterSet(django_filters.FilterSet):
    user = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SSHKey
        fields = ["user"]


class CreateSSHKeyRequestSerializer(serializers.Serializer):
    user = serializers.CharField(validators=[validate_unix_username])
    name = serializers.CharField(max_length=255)


class SSHKeySerializer(serializers.ModelSerializer):
    public_key = serializers.CharField(read_only=True)

    class Meta:
        model = SSHKey
        fields = [
            "id",
            "user",
            "public_key",
            "name",
            "fingerprint",
            "updated_at",
            "created_at",
        ]


class SwarmNodeSerializer(serializers.ModelSerializer):
    ssh_keys = SSHKeySerializer(many=True, read_only=True)

    class Meta:
        model = SwarmNode
        fields = [
            "id",
            "hostname",
            "role",
            "private_ip",
            "ssh_port",
            "status",
            "last_status_update",
            "docker_version",
            "is_build_server",
            "is_app_server",
            "is_initial_install_server",
            "cpus",
            "memory_bytes",
            "created_at",
            "updated_at",
            "ssh_keys",
        ]

    def get_fields(self):
        fields = super().get_fields()
        writable = {
            "private_ip",
            "ssh_port",
            "role",
            "is_build_server",
            "is_app_server",
        }

        for field_name, field in fields.items():
            field.read_only = field_name not in writable
        return fields
