from django.db import models
from typing import TYPE_CHECKING
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField
from django.utils.translation import gettext_lazy as _


if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    from zane_api.models.main import Project, Service
    from s3_targets.models import S3Credentials  # noqa: F401


class ContainerRegistryCredentials(TimestampedModel):
    ID_PREFIX = "reg_cred_"

    if TYPE_CHECKING:
        services: RelatedManager["Service"]
        build_registries: RelatedManager["BuildRegistry"]

    id = ShortUUIDField(  # type: ignore[arg-type]
        length=20,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class RegistryType(models.TextChoices):
        DOCKER_HUB = "DOCKER_HUB", _("Docker Hub")
        GITHUB = "GITHUB", _("GitHub Container Registry")
        GITLAB = "GITLAB", _("GitLab Container Registry")
        GOOGLE_ARTIFACT = "GOOGLE_ARTIFACT", _("Google Artifact Registry")
        AWS_ECR = "AWS_ECR", _("AWS Elastic Container Registry")
        GENERIC = "GENERIC", _("Generic Docker Registry (v2 API)")

    url = models.URLField(blank=False)
    password = models.TextField(blank=True, null=True)
    username = models.CharField(max_length=1024, null=True, blank=True)
    registry_type = models.CharField(
        max_length=32,
        choices=RegistryType.choices,
        default=RegistryType.GENERIC,
    )

    def __str__(self):
        return f"ContainerRegistry(registry_type={self.RegistryType(self.registry_type).label}, url={self.url}, username={self.username})"


# Create your models here
class BuildRegistry(TimestampedModel):
    if TYPE_CHECKING:
        projects: RelatedManager[Project]

    ID_PREFIX = "build_reg_"
    id = ShortUUIDField(primary_key=True, prefix=ID_PREFIX, length=20)  # type: ignore[arg-type]
    name = models.CharField(max_length=255)
    is_managed = models.BooleanField(default=True)
    is_global = models.BooleanField(default=False)

    # Only set if using an external registry, and only support `Generic` Registries (for now)
    external_registry = models.ForeignKey(
        ContainerRegistryCredentials,
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
    s3_credentials = models.ForeignKey["S3Credentials"](
        "s3_targets.S3Credentials",
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
