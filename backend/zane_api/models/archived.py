from django.conf import settings
from django.db import models

from .base import Project, DockerRegistryService
from ..utils import strip_slash_if_exists


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
    active_version = models.OneToOneField(
        to=Project,
        on_delete=models.SET_NULL,
        null=True,
        related_name="archived_version",
    )
    original_id = models.CharField(max_length=255)

    @classmethod
    def create_from_project(cls, project: Project):
        return cls.objects.create(
            slug=project.slug,
            owner=project.owner,
            active_version=project,
            original_id=project.id,
        )

    def __str__(self):
        return f"ArchivedProject({self.slug})"

    class Meta:
        indexes = [models.Index(fields=["slug"])]


class ArchivedURL(models.Model):
    domain = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    base_path = models.CharField(default="/")
    strip_prefix = models.BooleanField(default=True)

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
    name = models.CharField(max_length=255)
    containerPath = models.CharField(max_length=255)
    original_id = models.CharField(max_length=255)

    def __str__(self):
        return f"ArchivedVolume({self.name})"


class ArchivedPortConfiguration(TimestampArchivedModel):
    host = models.PositiveIntegerField(null=True)
    forwarded = models.PositiveIntegerField()


class ArchivedBaseService(TimestampArchivedModel):
    slug = models.SlugField(max_length=255)
    project = models.ForeignKey(to=ArchivedProject, on_delete=models.CASCADE)
    urls = models.ManyToManyField(to=ArchivedURL)
    volumes = models.ManyToManyField(to=ArchivedVolume)
    ports = models.ManyToManyField(to=ArchivedPortConfiguration)
    original_id = models.CharField(max_length=255)

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
    image = models.CharField(max_length=510)
    command = models.TextField(null=True, blank=True)
    docker_credentials_username = models.CharField(
        max_length=255, null=True, blank=True
    )
    docker_credentials_password = models.CharField(
        max_length=255, null=True, blank=True
    )

    @classmethod
    def create_from_service(
        cls, service: DockerRegistryService, parent: ArchivedProject
    ):
        archived_service = cls.objects.create(
            slug=service.slug,
            project=parent,
            command=service.command,
            original_id=service.id,
            docker_credentials_username=service.docker_credentials_username,
            docker_credentials_password=service.docker_credentials_password,
        )

        archived_volumes = ArchivedVolume.objects.bulk_create(
            [
                ArchivedVolume(
                    name=volume.name,
                    containerPath=volume.containerPath,
                    original_id=volume.id,
                )
                for volume in service.volumes.all()
            ]
        )
        archived_envs = ArchivedDockerEnvVariable.objects.bulk_create(
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
                )
                for url in service.urls.all()
            ]
        )

        archived_service.volumes.add(*archived_volumes)
        archived_service.ports.add(*archived_ports)
        archived_service.urls.add(*archived_urls)

        return archived_service
