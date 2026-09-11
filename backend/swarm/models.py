from django.db import models
from shortuuid.django_fields import ShortUUIDField
from webshell.models import SSHKey
from zane_api.models.base import TimestampedModel


# Create your models here.
class ServerNode(TimestampedModel):
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
    docker_version = models.CharField()
    ssh_key = models.ForeignKey(
        to=SSHKey,
        on_delete=models.SET_NULL,
        null=True,
    )
    last_status_update = models.DateTimeField(null=True)
