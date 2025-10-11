from django.db import models
from typing import TYPE_CHECKING
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    from zane_api.models.main import ContainerRegistryCredentials, Project


# Create your models here
class S3Credentials(TimestampedModel):
    ID_PREFIX = "s3_"
    id = ShortUUIDField(primary_key=True, prefix=ID_PREFIX, length=11)  # type: ignore[arg-type]
    name = models.CharField(max_length=255)
    bucket = models.CharField(max_length=255)
    region = models.CharField(max_length=100, default="us-east-1")
    access_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    endpoint_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return f"S3({self.bucket}@{self.region})"


class BuildRegistry(TimestampedModel):
    if TYPE_CHECKING:
        projects: RelatedManager[Project]
        external_registry: models.ForeignKey[ContainerRegistryCredentials | None]

    ID_PREFIX = "build_reg_"
    id = ShortUUIDField(primary_key=True, prefix=ID_PREFIX, length=20)  # type: ignore[arg-type]
    name = models.CharField(max_length=255)
    is_managed = models.BooleanField(default=True)
    is_global = models.BooleanField(default=False)

    # Only set if using an external registry, and only support `Generic` Registries (for now)
    external_registry = models.ForeignKey(
        "zane_api.ContainerRegistryCredentials",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="build_registries",
    )

    class StorageBackend(models.TextChoices):
        LOCAL = "LOCAL", _("Local Disk")
        S3 = "S3", _("Amazon S3")

    # Only meaningful for managed registries
    storage_backend = models.CharField(
        max_length=50,
        choices=StorageBackend.choices,
        default=StorageBackend.LOCAL,
    )
    s3_credentials = models.ForeignKey(
        S3Credentials,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    supports_multiarch = models.BooleanField(default=False)

    class Meta:  # type: ignore
        constraints = [
            models.UniqueConstraint(
                fields=["is_global"],
                condition=models.Q(is_global=True),
                name="unique_global_registry_per_instance",
            ),
        ]
