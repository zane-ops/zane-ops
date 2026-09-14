from rest_framework import serializers
from .models import SwarmNode


class SwarmNodeSerializer(serializers.ModelSerializer):
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
        ]
