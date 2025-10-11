from django.db import models
from typing import TYPE_CHECKING
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


# Create your models here.
class ContainerRegistry(TimestampedModel):
    ID_PREFIX = "cr_"
    id = ShortUUIDField(  # type: ignore[arg-type]
        length=14,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class RegistryType(models.TextChoices):
        DOCKER_HUB = "docker_hub", _("Docker Hub")
        GHCR = "ghcr", _("GitHub Container Registry")
        GITLAB = "gitlab", _("GitLab Container Registry")
        GENERIC = "generic", _("Generic Docker Registry (v2 API)")

    url = models.URLField(blank=False)
    password = models.TextField(blank=False)
    username = models.CharField(max_length=1024, null=True, blank=False)
    registry_type = models.CharField(
        max_length=32,
        choices=RegistryType.choices,
        default=RegistryType.GENERIC,
    )

    def __str__(self):
        return f"{self.RegistryType(self.registry_type).label} ({self.url})"
