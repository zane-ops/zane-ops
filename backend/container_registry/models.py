from django.db import models
from typing import TYPE_CHECKING, Self, cast
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from zane_api.validators import validate_url_domain

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    from zane_api.models.main import Project, Service
    from s3_targets.models import S3Credentials  # noqa: F401


class SharedRegistryCredentials(TimestampedModel):
    ID_PREFIX = "reg_cred_"

    if TYPE_CHECKING:
        services: RelatedManager["Service"]

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
    password = models.TextField()
    username = models.CharField(max_length=1024)
    registry_type = models.CharField(
        max_length=32,
        choices=RegistryType.choices,
        default=RegistryType.GENERIC,
    )
    slug = models.SlugField(unique=True)

    def __str__(self):
        return f"SharedRegistryCredentials(registry_type={self.RegistryType(self.registry_type).label}, url={self.url}, username={self.username})"

    class Meta:  # type: ignore
        ordering = ("created_at",)
        indexes = [models.Index(fields=["registry_type"])]


# Create your models here
class BuildRegistry(TimestampedModel):
    if TYPE_CHECKING:
        projects: RelatedManager[Project]

    ID_PREFIX = "build_reg_"
    id = ShortUUIDField(primary_key=True, prefix=ID_PREFIX, length=20)  # type: ignore[arg-type]
    name = models.CharField(max_length=255)
    is_managed = models.BooleanField(default=True)
    is_global = models.BooleanField(default=True)

    # For managed registries: inline credentials
    # For external registries: these fields reference the external registry
    registry_domain = models.CharField(
        max_length=2048, validators=[validate_url_domain]
    )
    registry_username = models.CharField(max_length=1024)
    registry_password = models.TextField()

    version = models.PositiveIntegerField(default=1)

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
    swarm_service_name = models.CharField(null=True)
    service_alias = models.CharField(null=True)

    @property
    def workflow_id(self) -> str:
        return f"deploy-{self.id}"

    @property
    def destroy_workflow_id(self) -> str:
        return f"destroy-{self.id}"

    @classmethod
    def generate_default_service_alias(cls, instance: Self) -> str:
        prefix = slugify(instance.name).lower()
        suffix = cast(str, instance.id).replace(instance.ID_PREFIX, "").lower()
        return f"zn-{prefix}-{suffix}"

    @classmethod
    def generate_default_swarm_service_name(cls, instance: Self) -> str:
        prefix = slugify(instance.name).lower()
        suffix = cast(str, instance.id).replace(instance.ID_PREFIX, "").lower()
        return f"srv-{prefix}-{suffix}"

    class Meta:  # type: ignore
        constraints = [
            models.UniqueConstraint(
                fields=["is_global"],
                condition=models.Q(is_global=True),
                name="unique_global_registry_per_instance",
            ),
        ]
