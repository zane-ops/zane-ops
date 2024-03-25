import uuid
from typing import List

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from shortuuid.django_fields import ShortUUIDField

from .validators import validate_url_domain, validate_crontab


class TimestampedModel(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Project(TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, unique=True)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-updated_at"]


class URL(models.Model):
    domain = models.CharField(
        max_length=1000, null=True, blank=True, validators=[validate_url_domain]
    )
    base_path = models.CharField(default="/")

    class Meta:
        unique_together = (
            "domain",
            "base_path",
        )


class BaseService(TimestampedModel):
    name = models.CharField(max_length=255)
    archived = models.BooleanField(default=False)
    slug = models.SlugField(max_length=255)
    project = models.ForeignKey(to=Project, on_delete=models.CASCADE)
    volumes = models.ManyToManyField(to="Volume")
    port_config = models.ManyToManyField(to="PortConfiguration")
    urls = models.ManyToManyField(to=URL)

    class Meta:
        abstract = True
        unique_together = (
            "slug",
            "project",
        )

    def __str__(self):
        return f"{self.name} ({self.slug})"


class PortConfiguration(models.Model):
    host = models.PositiveIntegerField(null=True, unique=True)
    forwarded = models.PositiveIntegerField()


class DockerRegistryService(BaseService):
    image = models.CharField(max_length=510)
    command = models.TextField(null=True, blank=True)
    docker_credentials_username = models.CharField(
        max_length=255, null=True, blank=True
    )
    docker_credentials_password = models.CharField(
        max_length=255, null=True, blank=True
    )


class GitRepositoryService(BaseService):
    previews_enabled = models.BooleanField(default=True)
    auto_deploy = models.BooleanField(default=True)
    preview_protected = models.BooleanField(default=True)
    delete_preview_after_merge = models.BooleanField(default=True)
    production_branch_name = models.CharField(max_length=255)
    repository_url = models.URLField(max_length=1000)
    build_success_webhook_url = models.URLField(null=True, blank=True)

    # for docker build context
    dockerfile_path = models.CharField(max_length=255, default="./Dockerfile")
    docker_build_context_dir = models.CharField(max_length=255, default=".")
    docker_cmd = models.CharField(max_length=255, null=True, blank=True)


class EnvVariable(models.Model):
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    is_for_production = models.BooleanField(default=True)
    project = models.ForeignKey(
        to=Project,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"EnvVariable ({self.key})"


class Volume(TimestampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    project = models.ForeignKey(
        to=Project,
        on_delete=models.CASCADE,
    )
    containerPath = models.CharField(max_length=255)

    class Meta:
        unique_together = (
            "slug",
            "project",
        )

    def __str__(self):
        return f"Volume ({self.slug})"


class BaseDeployment(models.Model):
    class DeploymentStatus(models.TextChoices):
        OFFLINE = "OFFLINE", _("Offline")
        ERROR = "ERROR", _("Error")
        LIVE = "LIVE", _("Live")
        PENDING = "PENDING", _("Pending")

    is_redeploy_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_production = models.BooleanField(default=True)
    deployment_status = models.CharField(
        max_length=10,
        choices=DeploymentStatus.choices,
        default=DeploymentStatus.PENDING,
    )
    env_variables = models.ManyToManyField(to="EnvVariable")
    logs = models.ManyToManyField(to="SimpleLog")
    http_logs = models.ManyToManyField(to="HttpLog")

    class Meta:
        abstract = True


class DockerDeployment(BaseDeployment):
    service = models.ForeignKey(to=DockerRegistryService, on_delete=models.CASCADE)
    hash = ShortUUIDField(length=11, max_length=11, unique=True)

    def get_task_id(self):
        return f"dpl-docker-{self.hash}-{self.service.slug}-{self.service.project.slug}"


class GitDeployment(BaseDeployment):
    class BuildStatus(models.TextChoices):
        ERROR = "ERROR", _("Error")
        SUCCESS = "SUCCESS", _("Success")
        PENDING = "PENDING", _("Pending")
        QUEUED = "QUEUED", _("Queued")

    build_status = models.CharField(
        max_length=10,
        choices=BuildStatus.choices,
        default=BuildStatus.QUEUED,
    )
    commit_hash = models.CharField(
        max_length=40
    )  # Typical length of a Git commit hash, but we will use the short version
    commit_message = models.TextField(blank=True)
    build_duration_in_ms = models.PositiveIntegerField(null=True)
    branch = models.CharField(max_length=255)
    service = models.ForeignKey(to=GitRepositoryService, on_delete=models.CASCADE)
    commit_author_username = models.CharField(max_length=255)
    commit_author_avatar_url = models.URLField(null=True)

    @property
    def image_tags(self) -> List[str]:
        tags = []  # type: List[str]
        if self.is_production:
            tags.append("latest")
        tags.append(f"{self.branch}-{self.commit_hash}")
        return list(map(tags, lambda tag: f"{self.image_name}:{tag}"))

    @property
    def image_name(self):
        project_prefix = self.service.project.slug
        service_prefix = self.service.slug
        return f"{project_prefix}-{service_prefix}"

    # @property
    # def domain(self):
    #     if self.is_production:
    #         return self.service.base_domain
    #
    #     return f"{self.service.project.slug}-{self.service.slug}-{self.commit_hash}.{self.service.base_domain}"

    def __str__(self):
        return f"{self.branch} - {self.commit_hash[:7]} - {self.build_status}"


class Log(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class SimpleLog(Log):
    class LogType(models.TextChoices):
        ERROR = "ERROR", _("Error")
        INFO = "INFO", _("Info")

    content = models.TextField(blank=True)
    log_type = models.CharField(
        max_length=10,
        choices=LogType.choices,
        default=LogType.INFO,
    )


class HttpLog(Log):
    class RequestMethod(models.TextChoices):
        GET = "GET", _("GET")
        POST = "POST", _("POST")
        PUT = "PUT", _("PUT")
        DELETE = "DELETE", _("DELETE")
        PATCH = "PATCH", _("PATCH")
        OPTIONS = "OPTIONS", _("OPTIONS")
        HEAD = "HEAD", _("HEAD")

    request_method = models.CharField(
        max_length=7,
        choices=RequestMethod.choices,
    )
    status = models.PositiveIntegerField()
    request_duration_ms = models.PositiveIntegerField()
    request_domain = models.URLField(max_length=1000)
    request_headers = models.JSONField()
    response_headers = models.JSONField()
    ip = models.GenericIPAddressField()
    path = models.CharField(max_length=2000)


class CRON(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=255)
    schedule = models.CharField(max_length=255, validators=[validate_crontab])
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class HttpCRON(CRON):
    class RequestMethod(models.TextChoices):
        GET = "GET", _("GET")
        POST = "POST", _("POST")
        PUT = "PUT", _("PUT")
        DELETE = "DELETE", _("DELETE")
        PATCH = "PATCH", _("PATCH")
        OPTIONS = "OPTIONS", _("OPTIONS")
        HEAD = "HEAD", _("HEAD")

    url = models.URLField(max_length=2000)
    headers = models.JSONField()
    body = models.JSONField()
    method = models.CharField(
        max_length=7,
        choices=RequestMethod.choices,
    )

    def __str__(self):
        return f"HTTP CRON {self.name}"


class ServiceCommandCRON(CRON):
    command = models.TextField()
    dockerService = models.ForeignKey(
        to=DockerRegistryService, null=True, on_delete=models.CASCADE
    )
    gitService = models.ForeignKey(
        to=GitRepositoryService, null=True, on_delete=models.CASCADE
    )

    def __str__(self):
        return f"HTTP CRON {self.name}"


class Worker(models.Model):
    idle_timeout_in_seconds = models.PositiveIntegerField()
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    is_public = models.BooleanField(default=False)
    domain = models.URLField(max_length=1000, null=True, blank=True)
    project = models.ForeignKey(
        to=Project,
        on_delete=models.CASCADE,
    )
    env_variables = models.ManyToManyField(to=EnvVariable)

    class Meta:
        abstract = True
        unique_together = (
            "slug",
            "project",
        )

    def __str__(self):
        return f"Worker ({self.name})"


class DockerRegistryWorker(Worker):
    base_image = models.CharField(max_length=255)
    docker_credentials_email = models.CharField(max_length=255, null=True, blank=True)
    docker_credentials_password = models.CharField(
        max_length=255, null=True, blank=True
    )

    def __str__(self):
        return f"Worker {self.name} based on {self.base_image}"


class GitRepositoryWorker(Worker):
    auto_deploy = models.BooleanField(default=True)
    repository_url = models.URLField(max_length=1000)

    # for docker build context
    dockerfile_path = models.CharField(max_length=255, default="./Dockerfile")
    docker_build_context_dir = models.CharField(max_length=255, default=".")
    docker_cmd = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Worker {self.name} from git repository: ({self.repository_url})"


class BaseWorkerDeployment(models.Model):
    class DeploymentStatus(models.TextChoices):
        ERROR = "ERROR", _("Error")
        SUCCESS = "SUCCESS", _("Success")
        PENDING = "PENDING", _("Pending")

    created_at = models.DateTimeField(auto_now_add=True)
    is_production = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=DeploymentStatus.choices,
        default=DeploymentStatus.PENDING,
    )
    logs = models.ManyToManyField(to="SimpleLog")

    class Meta:
        abstract = True


class DockerWorkerDeployment(BaseWorkerDeployment):
    worker = models.ForeignKey(to=DockerRegistryWorker, on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            "is_production",
            "worker",
        )


class GitWorkerDeployment(BaseWorkerDeployment):
    commit_hash = models.CharField(
        max_length=40
    )  # Typical length of a Git commit hash, but we will use the short version
    commit_message = models.TextField(blank=True)
    build_duration_in_ms = models.PositiveIntegerField()
    worker = models.ForeignKey(to=GitRepositoryWorker, on_delete=models.CASCADE)
    commit_author_username = models.CharField(max_length=255)
    commit_author_avatar_url = models.URLField(null=True)

    @property
    def image_tags(self) -> List[str]:
        tags = []  # type: List[str]
        if self.is_production:
            tags.append("latest")
        tags.append(f"{self.commit_hash}")
        return list(map(tags, lambda tag: f"{self.image_name}:{tag}"))

    @property
    def image_name(self):
        project_prefix = self.worker.project.slug
        service_prefix = self.worker.slug
        return f"{project_prefix}-{service_prefix}"

    @property
    def domain(self):
        if not self.worker.is_public:
            return None

        if self.is_production:
            return self.worker.domain

        return f"{self.project.slug}-{self.worker.slug}-{self.commit_hash}.{self.worker.domain}"

    class Meta:
        unique_together = (
            "is_production",
            "worker",
        )

    def __str__(self):
        return f"{self.worker.slug} - {self.commit_hash[:7]} - {self.status}"
