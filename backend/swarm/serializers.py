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

    def validate(self, attrs: dict):
        self.instance: SwarmNode | None

        cluster_roles: list[str] = attrs.get(
            "cluster_roles", self.instance.cluster_roles if self.instance else []
        )
        if not cluster_roles:
            raise serializers.ValidationError(
                "Nodes on ZaneOps should have at lease one cluster role"
            )

        attrs["cluster_roles"] = list(set(cluster_roles))
        return attrs

    class Meta:
        model = SwarmNode
        fields = [
            "id",
            "hostname",
            "swarm_role",
            "private_ip",
            "ssh_port",
            "status",
            "last_status_update",
            "docker_version",
            "cluster_roles",
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
            "swarm_role",
            "cluster_roles",
        }

        for field_name, field in fields.items():
            field.read_only = field_name not in writable
        return fields
