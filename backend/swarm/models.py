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

    hostname = models.CharField(unique=True)  # == swarm node Description.Hostname
    swarm_node_id = models.CharField(unique=True)
    role = models.CharField(choices=Role.choices)
    private_ip = models.GenericIPAddressField()  # overlay / VPC address
    public_ip = models.GenericIPAddressField(null=True)

    status = models.CharField(choices=Status.choices)
    last_status_update = models.DateTimeField(null=True)

    docker_version = models.CharField()
    ssh_key = models.ForeignKey(
        to=SSHKey,
        on_delete=models.SET_NULL,
        null=True,
    )
    # Can this run builds ?
    is_build_server = models.BooleanField(default=False)
    # Can this run user defined apps ?
    is_app_server = models.BooleanField(default=True)
    # The initial server from which ZaneOps was install
    is_initial_install_server = models.BooleanField(default=False)
    ssh_key = models.ForeignKey(SSHKey, on_delete=models.SET_NULL, null=True)
    ssh_user = models.CharField(default="root")
    ssh_port = models.PositiveIntegerField(default=22)

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
