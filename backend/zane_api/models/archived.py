from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import Project, DockerRegistryService
from ..utils import strip_slash_if_exists, datetime_to_timestamp_string


class TimestampArchivedModel(models.Model):
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class ArchivedProject(TimestampArchivedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)
    active_version = models.OneToOneField(
        to=Project,
        on_delete=models.SET_NULL,
        null=True,
        related_name="archived_version",
    )
    original_id = models.CharField(max_length=255)

    @property
    def workflow_id(self):
        return f"archive-{self.original_id}-{datetime_to_timestamp_string(self.archived_at)}"

    @classmethod
    def create_from_project(cls, project: Project):
        return cls.objects.create(
            slug=project.slug,
            owner=project.owner,
            active_version=project,
            original_id=project.id,
            description=project.description,
        )

    @classmethod
    def get_or_create_from_project(cls, project: Project):
        archived_version = (
            project.archived_version if hasattr(project, "archived_version") else None
        )
        if archived_version is None:
            archived_version = cls.objects.create(
                slug=project.slug,
                owner=project.owner,
                original_id=project.id,
                description=project.description,
            )
        return archived_version

    def __str__(self):
        return f"ArchivedProject({self.slug})"

    class Meta:
        indexes = [models.Index(fields=["slug"])]
        ordering = ["-archived_at"]


class ArchivedURL(models.Model):
    domain = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    base_path = models.CharField(default="/")
    strip_prefix = models.BooleanField(default=True)
    original_id = models.CharField(null=True)

    def __str__(self):
        base_path = (
            "/"
            if self.base_path == "/"
            else strip_slash_if_exists(
                self.base_path, strip_start=False, strip_end=True
            )
        )
        return f'ArchivedURL(domain="{self.domain}"), base_path="{base_path}")'


class ArchivedVolume(TimestampArchivedModel):
    class VolumeMode(models.TextChoices):
        READ_ONLY = "READ_ONLY", _("Read-Only")
        READ_WRITE = "READ_WRITE", _("Read-Write")

    mode = models.CharField(
        max_length=255,
        null=False,
        choices=VolumeMode.choices,
        default=VolumeMode.READ_WRITE,
    )
    name = models.CharField(max_length=255)
    container_path = models.CharField(max_length=255)
    host_path = models.CharField(max_length=255, null=True)
    original_id = models.CharField(max_length=255)

    def __str__(self):
        return f"ArchivedVolume({self.name})"


class ArchivedPortConfiguration(TimestampArchivedModel):
    host = models.PositiveIntegerField(null=True)
    forwarded = models.PositiveIntegerField()


class ArchivedBaseService(TimestampArchivedModel):
    slug = models.SlugField(max_length=255)
    urls = models.ManyToManyField(to=ArchivedURL)
    volumes = models.ManyToManyField(to=ArchivedVolume)
    ports = models.ManyToManyField(to=ArchivedPortConfiguration)
    original_id = models.CharField(max_length=255)
    resource_limits = models.JSONField(
        max_length=255,
        null=True,
    )
    healthcheck = models.JSONField(
        max_length=255,
        null=True,
    )

    class Meta:
        abstract = True


class BaseArchivedEnvVariable(TimestampArchivedModel):
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

    class Meta:
        abstract = True


class ArchivedDockerEnvVariable(BaseArchivedEnvVariable):
    service = models.ForeignKey(
        to="ArchivedDockerService",
        on_delete=models.CASCADE,
        related_name="env_variables",
    )


class ArchivedDockerService(ArchivedBaseService):
    image = models.CharField(max_length=510, null=False, blank=False)
    project = models.ForeignKey(
        to=ArchivedProject, on_delete=models.CASCADE, related_name="docker_services"
    )
    command = models.TextField(null=True, blank=True)
    credentials = models.JSONField(
        max_length=255,
        null=True,
    )
    deployments = models.JSONField(
        null=False, default=list
    )  # type: list[dict[str, str]]

    @property
    def workflow_id(self):
        return f"archive-{self.original_id}-{datetime_to_timestamp_string(self.archived_at)}"

    @classmethod
    def create_from_service(
        cls, service: DockerRegistryService, parent: ArchivedProject
    ):
        archived_service = cls.objects.create(
            image=service.image,
            slug=service.slug,
            project=parent,
            command=service.command,
            original_id=service.id,
            credentials=service.credentials,
            resource_limits=service.resource_limits,
            healthcheck=(
                dict(
                    type=service.healthcheck.type,
                    value=service.healthcheck.value,
                    interval_seconds=service.healthcheck.interval_seconds,
                    timeout_seconds=service.healthcheck.timeout_seconds,
                )
                if service.healthcheck is not None
                else None
            ),
            deployments=[
                dict(url=dpl.url, hash=dpl.hash) for dpl in service.deployments.all()
            ],
        )

        archived_volumes = ArchivedVolume.objects.bulk_create(
            [
                ArchivedVolume(
                    name=volume.name,
                    container_path=volume.container_path,
                    host_path=volume.host_path,
                    original_id=volume.id,
                    mode=volume.mode,
                )
                for volume in service.volumes.all()
            ]
        )
        ArchivedDockerEnvVariable.objects.bulk_create(
            [
                ArchivedDockerEnvVariable(
                    key=env.key,
                    value=env.value,
                    service=archived_service,
                )
                for env in service.env_variables.all()
            ]
        )

        archived_ports = ArchivedPortConfiguration.objects.bulk_create(
            [
                ArchivedPortConfiguration(host=port.host, forwarded=port.forwarded)
                for port in service.ports.all()
            ]
        )

        archived_urls = ArchivedURL.objects.bulk_create(
            [
                ArchivedURL(
                    domain=url.domain,
                    base_path=url.base_path,
                    strip_prefix=url.strip_prefix,
                    original_id=url.id,
                )
                for url in service.urls.all()
            ]
        )

        archived_service.volumes.add(*archived_volumes)
        archived_service.ports.add(*archived_ports)
        archived_service.urls.add(*archived_urls)

        return archived_service
