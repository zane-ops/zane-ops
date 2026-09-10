from django.db import models
from shortuuid.django_fields import ShortUUIDField
from webshell.models import SSHKey


class SwarmNodeType(models.TextChoices):
    MANAGER = "MANAGER", "Manager"
    WORKER = "WORKER", "Worker"


# Create your models here.
class ServerNode(models.Model):
    ID_PREFIX = "tok_"
    ID_LENGTH = 11

    id = ShortUUIDField(
        length=ID_LENGTH,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )  # type: ignore

    swarm_node = models.CharField(choices=SwarmNodeType.choices)
    swarm_id = models.CharField(unique=True)
    ip = models.CharField()
    docker_version = models.CharField()
    ssh_key = models.ForeignKey(
        to=SSHKey,
        on_delete=models.SET_NULL,
        null=True,
    )
