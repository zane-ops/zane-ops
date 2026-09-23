from rest_framework import serializers
from .models import SwarmNode
from webshell.serializers import SSHKeySerializer


class SwarmNodeSerializer(serializers.ModelSerializer):
    ssh_keys = SSHKeySerializer(many=True, read_only=True)

    class Meta:
        model = SwarmNode
        fields = [
            "id",
            "hostname",
            "role",
            "private_ip",
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
            "role",
            "is_build_server",
            "is_app_server",
        }

        for field_name, field in fields.items():
            field.read_only = field_name not in writable
        return fields
