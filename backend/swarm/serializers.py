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


IN_CLUSTER_STATUSES = [
    SwarmNode.Status.ACTIVE,
    SwarmNode.Status.DOWN,
    SwarmNode.Status.UNHEALTHY,
    SwarmNode.Status.PAUSED,
    SwarmNode.Status.DRAINED,
]


def check_if_cluster_roles_requirements_are_met(
    node: SwarmNode, new_cluster_roles: list[str]
) -> str | None:
    """
    The cluster needs at least one app server & one build server,
    returns the role that would not be held by any server anymore if `node` had `new_cluster_roles`
    """
    other_nodes = SwarmNode.objects.filter(status__in=IN_CLUSTER_STATUSES).exclude(
        id=node.id
    )
    for role in SwarmNode.ClusterRole:
        if (
            role in node.cluster_roles
            and role not in new_cluster_roles
            and not other_nodes.filter(cluster_roles__contains=[role]).exists()
        ):
            role_str = " ".join([part.capitalize() for part in role.split("_")])
            return role_str
    return None


class ProvisionSwarmNodeRequestSerializer(serializers.Serializer):
    target_ssh_key_id = serializers.IntegerField()
    main_ssh_key_id = serializers.IntegerField()

    def validate_root_key(self, key_id: int, node: SwarmNode) -> SSHKey:
        key = node.ssh_keys.filter(id=key_id).first()
        if key is None:
            raise serializers.ValidationError(
                f"No SSH key with the id `{key_id}` exists for the server `{node.private_ip}`"
            )
        if key.user != "root":
            raise serializers.ValidationError("The SSH key must be for the `root` user")
        return key

    def validate_target_ssh_key_id(self, value: int):
        node: SwarmNode = self.context["target_node"]
        self.validate_root_key(value, node)
        return value

    def validate_main_ssh_key_id(self, value: int):
        main_node: SwarmNode | None = self.context["main_node"]
        if main_node is None:
            raise serializers.ValidationError("No main server exists on the cluster")
        self.validate_root_key(value, main_node)
        return value

    def validate(self, attrs: dict):
        node: SwarmNode = self.context["target_node"]
        if node.is_initial_install_server:
            raise serializers.ValidationError(
                "The main server is already part of the cluster and cannot be provisioned"
            )
        if node.status not in [
            SwarmNode.Status.CREATED,
            SwarmNode.Status.FAILED,
            SwarmNode.Status.REMOVED,
        ]:
            raise serializers.ValidationError(
                f"Cannot provision a server with the status `{node.status}`, it is already part of the cluster"
            )
        return attrs


class DeprovisionSwarmNodeRequestSerializer(ProvisionSwarmNodeRequestSerializer):
    def validate(self, attrs: dict):
        node: SwarmNode = self.context["target_node"]
        if node.is_initial_install_server:
            raise serializers.ValidationError(
                "The main server cannot be removed from the cluster"
            )
        if node.status not in IN_CLUSTER_STATUSES:
            raise serializers.ValidationError(
                f"Cannot deprovision a server with the status `{node.status}`, it is not part of the cluster"
            )

        missing_role = check_if_cluster_roles_requirements_are_met(node, [])
        if missing_role is not None:
            raise serializers.ValidationError(
                f"The cluster needs at least one server with the role `{missing_role}`, this server is the last one"
            )
        return attrs


class UpdateSwarmNodeRolesRequestSerializer(serializers.Serializer):
    swarm_role = serializers.ChoiceField(choices=SwarmNode.Role.choices)
    cluster_roles = serializers.ListField(
        child=serializers.ChoiceField(choices=SwarmNode.ClusterRole.choices),
        allow_empty=False,
    )

    def validate_cluster_roles(self, value: list[str]):
        return list(set(value))

    def validate(self, attrs: dict):
        node: SwarmNode = self.context["node"]
        if (
            node.is_initial_install_server
            and attrs["swarm_role"] != SwarmNode.Role.MANAGER
        ):
            raise serializers.ValidationError(
                {"swarm_role": "The main server must stay a manager of the cluster"}
            )
        if node.swarm_node_id is None or node.status not in IN_CLUSTER_STATUSES:
            raise serializers.ValidationError(
                f"Cannot update the roles of a server with the status `{node.status}`, it is not part of the cluster"
            )

        missing_role = check_if_cluster_roles_requirements_are_met(
            node, attrs["cluster_roles"]
        )
        if missing_role is not None:
            raise serializers.ValidationError(
                {
                    "cluster_roles": f"The cluster needs at least one server with the role `{missing_role}`, this server is the last one"
                }
            )
        return attrs


class UpdateSwarmNodeSSHPortSerializer(serializers.ModelSerializer):
    class Meta:
        model = SwarmNode
        fields = ["ssh_port"]
        extra_kwargs = {"ssh_port": {"required": True}}


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
    def validate(self, attrs: dict):
        self.instance: SwarmNode | None

        cluster_roles: list[str] = attrs.get(
            "cluster_roles", self.instance.cluster_roles if self.instance else []
        )
        if not cluster_roles:
            raise serializers.ValidationError(
                "Nodes on ZaneOps should have at least one cluster role"
            )

        attrs["cluster_roles"] = list(set(cluster_roles))
        return attrs

    class Meta:
        model = SwarmNode
        fields = [
            "id",
            "hostname",
            "swarm_node_id",
            "swarm_role",
            "private_ip",
            "ssh_port",
            "status",
            "docker_version",
            "cluster_roles",
            "is_initial_install_server",
            "cpus",
            "memory_bytes",
            "created_at",
            "updated_at",
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


class FullSwarmNodeSerializer(serializers.ModelSerializer):
    ssh_keys = SSHKeySerializer(many=True, read_only=True)

    def validate(self, attrs: dict):
        self.instance: SwarmNode | None

        cluster_roles: list[str] = attrs.get(
            "cluster_roles", self.instance.cluster_roles if self.instance else []
        )
        if not cluster_roles:
            raise serializers.ValidationError(
                "Nodes on ZaneOps should have at least one cluster role"
            )

        attrs["cluster_roles"] = list(set(cluster_roles))
        return attrs

    class Meta:
        model = SwarmNode
        fields = [
            "id",
            "hostname",
            "swarm_node_id",
            "swarm_role",
            "private_ip",
            "ssh_port",
            "services",
            "status",
            "status_message",
            "last_status_update",
            "docker_version",
            "cluster_roles",
            "is_initial_install_server",
            "cpus",
            "memory_bytes",
            "created_at",
            "updated_at",
            "ssh_keys",
            "architecture",
        ]
