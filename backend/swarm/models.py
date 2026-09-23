from django.db import models
from shortuuid.django_fields import ShortUUIDField
from webshell.models import SSHKey
from zane_api.models.base import TimestampedModel


# Create your models here.
class SwarmNode(TimestampedModel):
    ID_PREFIX = "node_"
    ID_LENGTH = 11

    class Role(models.TextChoices):
        MANAGER = "MANAGER", "Manager"
        WORKER = "WORKER", "Worker"

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
    role = models.CharField(choices=Role.choices)
    hostname = models.CharField(
        unique=True, null=True
    )  # == swarm node Description.Hostname
    private_ip = models.GenericIPAddressField()  # overlay / VPC address

    status = models.CharField(choices=Status.choices, default=Status.PROVISIONING)
    last_status_update = models.DateTimeField(null=True)

    docker_version = models.CharField(null=True)
    # Can this run builds ?
    is_build_server = models.BooleanField(default=False)
    # Can this run user defined apps ?
    is_app_server = models.BooleanField(default=True)
    # The initial server from which ZaneOps was install
    is_initial_install_server = models.BooleanField(default=False)
    ssh_keys = models.ManyToManyField(to=SSHKey, related_name="servers")

    # server limits
    cpus = models.PositiveIntegerField(null=True)
    memory_bytes = models.BigIntegerField(null=True)

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
