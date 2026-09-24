import base64
import hashlib
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.db import models
from shortuuid.django_fields import ShortUUIDField
from zane_api.models.base import TimestampedModel
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import ArrayField

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class SwarmNode(TimestampedModel):
    if TYPE_CHECKING:
        ssh_keys: RelatedManager["SSHKey"]

    ID_PREFIX = "node_"
    ID_LENGTH = 11

    class Role(models.TextChoices):
        MANAGER = "MANAGER", "Manager"
        WORKER = "WORKER", "Worker"

    class ClusterRole(models.TextChoices):
        # Can this run builds ?
        BUILD_SERVER = "BUILD_SERVER", "Build Server"
        # Can this run user defined apps ?
        APP_SERVER = "APP_SERVER", "App Server"

    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PROVISIONING = "PROVISIONING", "Provisioning"
        READY = "READY", "Ready"
        DOWN = "DOWN", "Down"
        DRAINED = "DRAINED", "Drained"
        FAILED = "FAILED", "Failed"

    id = ShortUUIDField(
        length=ID_LENGTH,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )  # type: ignore

    swarm_node_id = models.CharField(unique=True, null=True)
    swarm_role = models.CharField(choices=Role.choices)
    hostname = models.CharField(
        unique=True, null=True
    )  # == swarm node Description.Hostname
    private_ip = models.GenericIPAddressField(unique=True)  # overlay / VPC address

    status = models.CharField(choices=Status.choices, default=Status.CREATED)
    last_status_update = models.DateTimeField(null=True)

    docker_version = models.CharField(null=True)
    cluster_roles = ArrayField(
        base_field=models.CharField(max_length=255, choices=ClusterRole.choices),
        default=list,
        blank=True,
    )
    # The initial server from which ZaneOps was install
    is_initial_install_server = models.BooleanField(default=False)

    # server limits
    cpus = models.PositiveIntegerField(null=True)
    memory_bytes = models.BigIntegerField(null=True)

    ssh_port = models.PositiveIntegerField(
        default=22,
        validators=[
            # Valid port range of unix
            MinValueValidator(1),
            MaxValueValidator(65_535),
        ],
    )

    @property
    def build_task_queue(self) -> str:
        """
        Queue name for running builds on this node specifically. Only nodes
        with `is_build_server=True` run a worker on this queue.
        """
        return f"build-{self.hostname}"

    @property
    def node_task_queue(self) -> str:
        """
        Queue name for running node-local tasks: health checks, container
        metrics, exec/logs against the local Docker socket, and all Temporal
        schedules.
        Every node runs a worker on its own queue, always.
        """
        return f"node-{self.hostname}"

    class Meta:  # type: ignore
        constraints = [
            models.UniqueConstraint(
                fields=["is_initial_install_server"],
                condition=models.Q(is_initial_install_server=True),
                name="unique_initial_install_server",
            ),
        ]


class SSHKey(TimestampedModel):
    id: int
    node = models.ForeignKey(
        to=SwarmNode, on_delete=models.CASCADE, related_name="ssh_keys"
    )
    user = models.CharField(max_length=255, blank=False)
    public_key = models.TextField(blank=False)
    private_key = models.TextField(blank=False)
    name = models.CharField(max_length=255, blank=False)
    fingerprint = models.CharField(null=True, default=None)

    @classmethod
    def create_key_pair(cls) -> tuple[str, str]:
        # Generate a new RSA key pair
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        private_key_str = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_key = private_key.public_key()
        public_key_str = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode()

        return (public_key_str, private_key_str)

    @classmethod
    def generate_fingerprint(cls, public_key: str) -> str:
        # Read the OpenSSH‐formatted public key and extract the Base64 blob
        key_blob = public_key.strip().split()[1]

        # Decode the blob, hash it with SHA-256, then Base64-encode without padding
        blob = base64.b64decode(key_blob)
        digest = hashlib.sha256(blob).digest()
        fingerprint = base64.b64encode(digest).rstrip(b"=").decode("ascii")

        return f"SHA256:{fingerprint}"
