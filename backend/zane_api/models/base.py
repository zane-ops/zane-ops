# type: ignore
import time
import uuid
from typing import Optional

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from faker import Faker
from shortuuid.django_fields import ShortUUIDField
from django.utils import timezone
from ..utils import (
    strip_slash_if_exists,
    datetime_to_timestamp_string,
    generate_random_chars,
)
from ..validators import validate_url_domain, validate_url_path, validate_env_name
from django.db.models import Manager


class TimestampedModel(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Project(TimestampedModel):
    environments: Manager["Environment"]
    services: Manager["Service"]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    slug = models.SlugField(max_length=255, unique=True)
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix="prj_",
    )
    description = models.TextField(blank=True, null=True)

    @property
    def production_env(self):
        return self.environments.get(name=Environment.PRODUCTION_ENV)

    @property
    async def aproduction_env(self):
        return await self.environments.aget(name=Environment.PRODUCTION_ENV)

    @property
    def create_task_id(self):
        return f"create-{self.id}-{datetime_to_timestamp_string(self.created_at)}"

    def __str__(self):
        return f"Project({self.slug})"

    class Meta:
        ordering = ["-updated_at"]


class URL(models.Model):
    ID_PREFIX = "url_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    domain = models.CharField(max_length=1000, validators=[validate_url_domain])
    base_path = models.CharField(default="/", validators=[validate_url_path])
    strip_prefix = models.BooleanField(default=True)
    redirect_to = models.JSONField(max_length=2000, null=True)
    associated_port = models.PositiveIntegerField(null=True)

    @classmethod
    def generate_default_domain(cls, service: "BaseService"):
        return f"{service.project.slug}-{service.slug}-{generate_random_chars(10).lower()}.{settings.ROOT_DOMAIN}"

    def __repr__(self):
        base_path = (
            "/"
            if self.base_path == "/"
            else strip_slash_if_exists(
                self.base_path, strip_start=False, strip_end=True
            )
        )
        return f'URL(domain="{self.domain}"), base_path="{base_path}")'

    def __str__(self):
        base_path = (
            "/"
            if self.base_path == "/"
            else strip_slash_if_exists(
                self.base_path, strip_start=False, strip_end=True
            )
        )
        return f"{self.domain}{base_path}"

    class Meta:
        unique_together = (
            "domain",
            "base_path",
        )


class HealthCheck(models.Model):
    ID_PREFIX = "htc_"
    DEFAULT_TIMEOUT_SECONDS = 60
    DEFAULT_INTERVAL_SECONDS = 15
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class HealthCheckType(models.TextChoices):
        COMMAND = "COMMAND", _("Command")
        PATH = "PATH", _("Path")

    type = models.CharField(
        max_length=255,
        null=False,
        choices=HealthCheckType.choices,
        default=HealthCheckType.PATH,
    )
    value = models.CharField(max_length=255, null=False, default="/")
    interval_seconds = models.PositiveIntegerField(default=DEFAULT_INTERVAL_SECONDS)
    timeout_seconds = models.PositiveIntegerField(default=DEFAULT_TIMEOUT_SECONDS)
    associated_port = models.PositiveIntegerField(null=True)


class BaseService(TimestampedModel):
    slug = models.SlugField(max_length=255)
    project = models.ForeignKey(
        to=Project, on_delete=models.CASCADE, related_name="services"
    )
    volumes = models.ManyToManyField(to="Volume")
    ports = models.ManyToManyField(to="PortConfiguration")
    urls = models.ManyToManyField(to=URL)
    healthcheck = models.ForeignKey(
        to=HealthCheck, null=True, on_delete=models.SET_NULL
    )
    network_alias = models.CharField(max_length=300, null=True)
    resource_limits = models.JSONField(
        max_length=255,
        null=True,
    )
    deploy_token = models.CharField(max_length=25, null=True, unique=True)
    configs = models.ManyToManyField(to="Config")

    @property
    def host_volumes(self):
        return self.volumes.filter(host_path__isnull=False)

    @property
    def docker_volumes(self):
        return self.volumes.filter(host_path__isnull=True)

    class Meta:
        abstract = True

    def delete_resources(self):
        self.ports.filter().delete()
        self.urls.filter().delete()
        self.volumes.filter().delete()
        self.configs.filter().delete()
        if self.healthcheck is not None:
            self.healthcheck.delete()


class PortConfiguration(models.Model):
    ID_PREFIX = "prt_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    host = models.PositiveIntegerField(default=0)
    forwarded = models.PositiveIntegerField()

    def __str__(self):
        host_port = 80 if self.host is None else self.host
        return f"PortConfiguration({host_port} -> {self.forwarded})"

    class Meta:
        indexes = [models.Index(fields=["host"])]


class BaseEnvVariable(models.Model):
    key = models.CharField(max_length=255, validators=[validate_env_name])
    value = models.TextField(blank=True)

    class Meta:
        abstract = True


class EnvVariable(BaseEnvVariable):
    ID_PREFIX = "env_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    service: models.ForeignKey["Service"] = models.ForeignKey(
        to="Service",
        on_delete=models.CASCADE,
        related_name="env_variables",
    )

    def __str__(self):
        return f"DockerEnvVariable({self.key})"

    class Meta:
        unique_together = ["key", "service"]


class Service(BaseService):
    deployments: Manager["Deployment"]
    changes: Manager["DeploymentChange"]
    ports: Manager["PortConfiguration"]
    env_variables: Manager[EnvVariable]
    urls: Manager[URL]
    volumes: Manager["Volume"]
    configs: Manager["Config"]
    project_id: str

    class ServiceType(models.TextChoices):
        DOCKER_REGISTRY = "DOCKER_REGISTRY", _("Docker repository")
        GIT_REPOSITORY = "GIT_REPOSITORY", _("Git repository")

    class Builder(models.TextChoices):
        DOCKERFILE = "DOCKERFILE", _("Dockerfile")
        # NIXPACKS = "Nixpacks", _("Nixpacks")
        # STATIC_DIR = "STATIC_DIR", _("Static directory")

    ID_PREFIX = "srv_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    image = models.CharField(max_length=510, null=True)
    credentials = models.JSONField(
        max_length=255,
        null=True,
    )
    command = models.TextField(null=True, blank=True)

    environment: models.ForeignKey["Environment"] = models.ForeignKey(
        to="Environment",
        on_delete=models.CASCADE,
        related_name="services",
    )

    type = models.CharField(
        max_length=15, choices=ServiceType.choices, default=ServiceType.DOCKER_REGISTRY
    )

    # git attributes
    repository_url = models.URLField(max_length=2048, null=True)
    branch_name = models.CharField(max_length=255, null=True)
    commit_sha = models.CharField(max_length=45, null=True)
    builder = models.CharField(max_length=20, choices=Builder.choices, null=True)
    dockerfile_builder_options = models.JSONField(null=True)
    # An JSON object with this content :
    # {
    #    "build_context_dir": "./",
    #    "dockerfile_path": "./Dockerfile",
    #    "build_target": "builder",
    # }

    # TODO: later, when we will support pull requests environments and auto-deploy
    # auto_deploy = models.BooleanField(default=False)
    # git_app = models.ForeignKey(null=True)
    # previews_enabled = models.BooleanField(default=False)
    # delete_preview_after_merge = models.BooleanField(default=True)

    def __str__(self):
        return f"Service({self.slug})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "project", "environment"],
                name="unique_slug_per_env_and_project",
            ),
            models.UniqueConstraint(
                fields=["network_alias", "project", "environment"],
                name="unique_network_alias_per_env_and_project",
            ),
        ]

    @property
    def unprefixed_id(self):
        return self.id.replace(self.ID_PREFIX, "") if self.id is not None else None

    @property
    def http_logs(self):
        return HttpLog.objects.filter(service_id=self.id)

    @property
    def metrics(self):
        return ServiceMetrics.objects.filter(service=self)

    @property
    def network_aliases(self):
        return (
            [
                f"{self.network_alias}.{settings.ZANE_INTERNAL_DOMAIN}",
                self.network_alias,
            ]
            if self.network_alias is not None
            else []
        )

    @property
    def system_env_variables(self) -> list[dict[str, str]]:
        domains = ",".join(
            [url.domain for url in self.urls.filter(associated_port__isnull=False)]
        )
        return [
            {
                "key": "ZANE",
                "value": "true",
                "comment": "Is the service deployed on zaneops?",
            },
            {
                "key": "ZANE_DOMAINS",
                "value": domains,
                "comment": "comma separated list of the all the domains where this service is accessible",
            },
            {
                "key": "ZANE_ENVIRONMENT",
                "value": f"{self.environment.name}",
                "comment": "The current environment where the service is deployed",
            },
            {
                "key": "ZANE_PRIVATE_DOMAIN",
                "value": f"{self.network_alias}.{settings.ZANE_INTERNAL_DOMAIN}",
                "comment": "The domain used to reach this service on the same project",
            },
            {
                "key": "ZANE_DEPLOYMENT_TYPE",
                "value": (
                    "docker"
                    if self.type == Service.ServiceType.DOCKER_REGISTRY
                    else "git"
                ),
                "comment": "The type of the service",
            },
            {
                "key": "ZANE_SERVICE_ID",
                "value": self.id,
                "comment": "The service ID",
            },
            {
                "key": "ZANE_SERVICE_NAME",
                "value": self.slug,
                "comment": "The name of this service",
            },
            {
                "key": "ZANE_PROJECT_ID",
                "value": self.project_id,
                "comment": "The id for the project this service belongs to",
            },
            {
                "key": "ZANE_DEPLOYMENT_SLOT",
                "value": "{{deployment.slot}}",
                "comment": "The slot for each deployment it can be `blue` or `green`, this is also sent as the header `x-zane-dpl-slot`",
            },
            {
                "key": "ZANE_DEPLOYMENT_HASH",
                "value": "{{deployment.hash}}",
                "comment": "The hash of each deployment, this is also sent as a header `x-zane-dpl-hash`",
            },
        ]

    @property
    def latest_production_deployment(self):
        return (
            self.deployments.filter(is_current_production=True)
            .select_related("service", "service__project")
            .prefetch_related(
                "service__volumes",
                "service__urls",
                "service__ports",
                "service__env_variables",
            )
            .order_by("-queued_at")
            .first()
        )

    @property
    async def alatest_production_deployment(self):
        return await (
            self.deployments.filter(is_current_production=True)
            .select_related("service", "service__project", "service__healthcheck")
            .prefetch_related(
                "service__volumes",
                "service__urls",
                "service__ports",
                "service__env_variables",
            )
            .order_by("-queued_at")
            .afirst()
        )

    @property
    def unapplied_changes(self):
        return self.changes.filter(applied=False)

    @property
    def applied_changes(self):
        return self.changes.filter(applied=True)

    @property
    def last_queued_deployment(self):
        return (
            self.deployments.filter(
                is_current_production=False,
                status=Deployment.DeploymentStatus.QUEUED,
            )
            .prefetch_related(
                "service__volumes",
                "service__urls",
                "service__ports",
                "service__env_variables",
            )
            .order_by("-queued_at")
            .first()
        )

    def apply_pending_changes(self, deployment: "Deployment"):
        for change in self.unapplied_changes:
            match (change.field, self.type):
                case DeploymentChange.ChangeField.COMMAND, __:
                    setattr(self, change.field, change.new_value)
                case (
                    DeploymentChange.ChangeField.SOURCE,
                    Service.ServiceType.DOCKER_REGISTRY,
                ):
                    self.image = change.new_value.get("image")
                    credentials = change.new_value.get("credentials")

                    self.credentials = (
                        None
                        if credentials is None
                        else {
                            "username": credentials.get("username"),
                            "password": credentials.get("password"),
                        }
                    )
                case (
                    DeploymentChange.ChangeField.GIT_SOURCE,
                    Service.ServiceType.GIT_REPOSITORY,
                ):
                    self.repository_url = change.new_value.get("repository_url")
                    self.branch_name = change.new_value.get("branch_name")
                    self.commit_sha = change.new_value.get("commit_sha", "HEAD")
                case (
                    DeploymentChange.ChangeField.BUILDER,
                    Service.ServiceType.GIT_REPOSITORY,
                ):
                    builder_options = change.new_value["options"]
                    match change.new_value.get("builder"):
                        case Service.Builder.DOCKERFILE:
                            self.builder = change.new_value.get("builder")
                            self.dockerfile_builder_options = {
                                "dockerfile_path": builder_options["dockerfile_path"],
                                "build_context_dir": builder_options[
                                    "build_context_dir"
                                ],
                                "build_stage_target": builder_options[
                                    "build_stage_target"
                                ],
                            }
                        case _:
                            raise NotImplementedError(
                                f"This builder `{change.new_value.get('builder')}` type has not yet been implemented"
                            )
                case DeploymentChange.ChangeField.RESOURCE_LIMITS, __:
                    if change.new_value is None:
                        self.resource_limits = None
                        continue
                    self.resource_limits = {
                        "cpus": change.new_value.get("cpus"),
                        "memory": change.new_value.get("memory"),
                    }
                case DeploymentChange.ChangeField.HEALTHCHECK, __:
                    if change.new_value is None:
                        if self.healthcheck is not None:
                            self.healthcheck.delete()
                            self.healthcheck = None
                        continue

                    if self.healthcheck is None:
                        self.healthcheck = HealthCheck()

                    self.healthcheck.type = change.new_value.get("type")
                    self.healthcheck.value = change.new_value.get("value")
                    self.healthcheck.associated_port = change.new_value.get(
                        "associated_port"
                    )
                    self.healthcheck.timeout_seconds = (
                        change.new_value.get("timeout_seconds")
                        or HealthCheck.DEFAULT_TIMEOUT_SECONDS
                    )
                    self.healthcheck.interval_seconds = (
                        change.new_value.get("interval_seconds")
                        or HealthCheck.DEFAULT_INTERVAL_SECONDS
                    )
                    self.healthcheck.save()
                case DeploymentChange.ChangeField.VOLUMES, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        fake = Faker()
                        Faker.seed(time.monotonic())
                        self.volumes.add(
                            Volume.objects.create(
                                container_path=change.new_value.get("container_path"),
                                host_path=change.new_value.get("host_path"),
                                mode=change.new_value.get("mode"),
                                name=change.new_value.get("name", fake.slug().lower()),
                            )
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.volumes.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        volume = self.volumes.get(id=change.item_id)
                        volume.host_path = change.new_value.get("host_path")
                        volume.container_path = change.new_value.get("container_path")
                        volume.mode = change.new_value.get("mode")
                        volume.name = change.new_value.get("name", volume.name)
                        volume.save()
                case DeploymentChange.ChangeField.CONFIGS, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        fake = Faker()
                        Faker.seed(time.monotonic())
                        self.configs.add(
                            Config.objects.create(
                                mount_path=change.new_value.get("mount_path"),
                                contents=change.new_value.get("contents"),
                                name=change.new_value.get("name", fake.slug().lower()),
                                language=change.new_value.get("language", "plaintext"),
                            )
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.configs.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        config = self.configs.get(id=change.item_id)
                        config.mount_path = change.new_value.get(
                            "mount_path", config.mount_path
                        )
                        new_contents = change.new_value.get("contents", config.contents)

                        if config.contents != new_contents:
                            config.version += 1

                        config.contents = new_contents
                        config.name = change.new_value.get("name", config.name)
                        config.language = change.new_value.get(
                            "language", config.language
                        )
                        config.save()
                case DeploymentChange.ChangeField.ENV_VARIABLES, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        EnvVariable.objects.create(
                            key=change.new_value.get("key"),
                            value=change.new_value.get("value"),
                            service=self,
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.env_variables.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        env = self.env_variables.get(id=change.item_id)
                        env.key = change.new_value.get("key")
                        env.value = change.new_value.get("value")
                        env.save()
                case DeploymentChange.ChangeField.URLS, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        self.urls.add(
                            URL.objects.create(
                                domain=change.new_value.get("domain"),
                                base_path=change.new_value.get("base_path"),
                                strip_prefix=change.new_value.get("strip_prefix"),
                                redirect_to=change.new_value.get("redirect_to"),
                                associated_port=change.new_value.get("associated_port"),
                            )
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.urls.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        url = self.urls.get(id=change.item_id)
                        url.domain = change.new_value.get("domain")
                        url.base_path = change.new_value.get("base_path")
                        url.strip_prefix = change.new_value.get("strip_prefix")
                        url.redirect_to = change.new_value.get("redirect_to")
                        url.associated_port = change.new_value.get("associated_port")
                        url.save()
                case DeploymentChange.ChangeField.PORTS, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        self.ports.add(
                            PortConfiguration.objects.create(
                                host=change.new_value.get("host"),
                                forwarded=change.new_value.get("forwarded"),
                            )
                        )

                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.ports.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        port = self.ports.get(id=change.item_id)
                        port.host = change.new_value.get("host")
                        port.forwarded = change.new_value.get("forwarded")
                        port.save()

        self.unapplied_changes.update(applied=True, deployment=deployment)
        self.save()
        self.refresh_from_db()

    def clone(self, environment: "Environment"):
        service = Service.objects.create(
            slug=self.slug,
            environment=environment,
            project=self.project,
            network_alias=self.network_alias,
            deploy_token=generate_random_chars(20),
        )
        return service

    def add_change(self, change: "DeploymentChange"):
        change.service = self
        match change.field:
            case (
                DeploymentChange.ChangeField.BUILDER
                | DeploymentChange.ChangeField.GIT_SOURCE
                | DeploymentChange.ChangeField.SOURCE
                | DeploymentChange.ChangeField.COMMAND
                | DeploymentChange.ChangeField.HEALTHCHECK
                | DeploymentChange.ChangeField.RESOURCE_LIMITS
            ):
                change_for_field = self.unapplied_changes.filter(
                    field=change.field
                ).first()
                if change_for_field is not None:
                    change_for_field.new_value = change.new_value
                else:
                    change_for_field = change
                change_for_field.save()
            case _:
                change.save()


class ServiceMetrics(TimestampedModel):
    cpu_percent = models.FloatField()
    memory_bytes = models.PositiveBigIntegerField()
    net_tx_bytes = models.PositiveBigIntegerField()
    net_rx_bytes = models.PositiveBigIntegerField()
    disk_read_bytes = models.PositiveBigIntegerField()
    disk_writes_bytes = models.PositiveBigIntegerField()

    service = models.ForeignKey(to=Service, on_delete=models.CASCADE)
    deployment = models.ForeignKey["Deployment"](
        to="Deployment", on_delete=models.CASCADE
    )

    class Meta:
        indexes = [models.Index(fields=["created_at"])]


class Volume(TimestampedModel):
    ID_PREFIX = "vol_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)

    class VolumeMode(models.TextChoices):
        READ_ONLY = "READ_ONLY", _("Read-Only")
        READ_WRITE = "READ_WRITE", _("Read-Write")

    mode = models.CharField(
        max_length=255,
        null=False,
        choices=VolumeMode.choices,
        default=VolumeMode.READ_WRITE,
    )
    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        validators=[MinLengthValidator(limit_value=1)],
    )
    container_path = models.CharField(max_length=255)
    host_path = models.CharField(
        max_length=255, null=True, validators=[validate_url_path]
    )

    def __str__(self):
        return f"Volume({self.name})"

    class Meta:
        indexes = [
            models.Index(fields=["host_path"]),
            models.Index(fields=["container_path"]),
        ]


class Config(TimestampedModel):
    ID_PREFIX = "cf_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)

    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        validators=[MinLengthValidator(limit_value=1)],
    )
    mount_path = models.CharField(max_length=255)
    contents = models.TextField(blank=True)
    language = models.CharField(default="plaintext", max_length=255)
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Config({self.name})"

    class Meta:
        indexes = [
            models.Index(fields=["mount_path"]),
            models.Index(fields=["version"]),
        ]


class DeploymentURL(models.Model):
    domain = models.URLField()
    port = models.PositiveIntegerField(default=80)
    deployment: models.ForeignKey["Deployment"] = models.ForeignKey(
        to="Deployment",
        on_delete=models.CASCADE,
        related_name="urls",
    )

    @classmethod
    def generate_for_deployment(
        cls,
        deployment: "Deployment",
        port: int,
        service: "Service",
    ):
        return cls.objects.create(
            domain=f"{service.project.slug}-{service.slug}-{deployment.hash.replace('_', '-')}-{generate_random_chars(10)}.{settings.ROOT_DOMAIN}".lower(),
            port=port,
            deployment=deployment,
        )

    class Meta:
        indexes = [models.Index(fields=["domain"])]


class BaseDeployment(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        abstract = True


class Deployment(BaseDeployment):
    environment_id: str
    HASH_PREFIX = "dpl_dkr_"
    urls = Manager["DeploymentURL"]
    changes = Manager["DeploymentChange"]
    hash = ShortUUIDField(length=11, max_length=255, unique=True, prefix=HASH_PREFIX)

    is_redeploy_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True)

    class DeploymentTriggerMethod(models.TextChoices):
        MANUAL = "MANUAL", _("Manual")
        AUTO = "AUTO", _("Automatic")
        WEBHOOK = "WEBHOOK", _("Webhook")

    class BuildStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        PENDING = "PENDING", _("Pending")
        SUCCESS = "SUCCESS", _("Success")
        ERROR = "ERROR", _("Error")

    class DeploymentStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        CANCELLED = "CANCELLED", _("Cancelled")
        CANCELLING = "CANCELLING", _("Cancelling")
        FAILED = "FAILED", _("Failed")
        PREPARING = "PREPARING", _("Preparing")
        BUILDING = "BUILDING", _("Building")
        STARTING = "STARTING", _("Starting")
        RESTARTING = "RESTARTING", _("Restarting")
        HEALTHY = "HEALTHY", _("Healthy")
        UNHEALTHY = "UNHEALTHY", _("Unhealthy")
        REMOVED = "REMOVED", _("Removed")
        SLEEPING = "SLEEPING", _("Sleeping")

    class DeploymentSlot(models.TextChoices):
        BLUE = "BLUE", _("Blue")
        GREEN = "GREEN", _("Green")

    slot = models.CharField(
        max_length=10,
        choices=DeploymentSlot.choices,
        default=DeploymentSlot.BLUE,
    )

    status = models.CharField(
        max_length=10,
        choices=DeploymentStatus.choices,
        default=DeploymentStatus.QUEUED,
    )
    status_reason = models.TextField(null=True, blank=True)
    is_current_production = models.BooleanField(default=False)
    service = models.ForeignKey(
        to=Service, on_delete=models.CASCADE, related_name="deployments"
    )
    service_snapshot = models.JSONField(null=True)
    commit_message = models.TextField(default="update service")

    build_status = models.CharField(
        max_length=10,
        choices=BuildStatus.choices,
        default=BuildStatus.QUEUED,
    )

    trigger_method = models.CharField(
        max_length=15,
        choices=DeploymentTriggerMethod.choices,
        default=DeploymentTriggerMethod.MANUAL,
    )
    commit_sha = models.CharField(max_length=45, null=True)
    commit_author_name = models.TextField(max_length=1024, null=True)
    pull_request_number = models.PositiveIntegerField(null=True)
    ignore_build_cache = models.BooleanField(default=False)
    build_started_at = models.DateTimeField(null=True)
    build_finished_at = models.DateTimeField(null=True)

    @classmethod
    def get_next_deployment_slot(
        cls,
        latest_production_deployment: Optional["Deployment"],
    ) -> str:
        if (
            latest_production_deployment is not None
            and latest_production_deployment.slot == Deployment.DeploymentSlot.BLUE
            and latest_production_deployment.status
            != Deployment.DeploymentStatus.FAILED
            # 👆🏽 technically this can only be true for the initial deployment
            # for the next deployments, when they fail, they will not be promoted to production
        ):
            return Deployment.DeploymentSlot.GREEN
        return Deployment.DeploymentSlot.BLUE

    @property
    def workflow_id(self):
        return f"deploy-{self.service.id}-{self.service.project_id}"

    @property
    def image_tag(self):
        return f"{self.service.unprefixed_id}:{self.commit_sha}".lower()

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.service.project_id}"

    @property
    def metrics_schedule_id(self):
        return f"metrics-{self.hash}-{self.service_id}-{self.service.project_id}"

    @property
    def unprefixed_hash(self) -> str:
        return None if self.hash is None else self.hash.replace(self.HASH_PREFIX, "")

    @property
    def network_aliases(self):
        aliases = []
        if self.service is not None and len(self.service.network_aliases) > 0:
            aliases = self.service.network_aliases + [self.network_alias]
        return aliases

    @property
    def network_alias(self):
        return f"{self.service.network_alias}-{self.service.environment_id.replace(Environment.ID_PREFIX, '')}.{self.slot.lower()}.{settings.ZANE_INTERNAL_DOMAIN}"

    class Meta:
        ordering = ("-queued_at",)
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["build_status"]),
            models.Index(fields=["is_current_production"]),
        ]

    @property
    def http_logs(self):
        return HttpLog.objects.filter(deployment_id=self.hash)

    def __str__(self):
        return f"DockerDeployment(hash={self.hash}, service={self.service.slug}, project={self.service.project.slug})"


class BaseDeploymentChange(TimestampedModel):
    class ChangeType(models.TextChoices):
        UPDATE = "UPDATE", _("update")
        DELETE = "DELETE", _("delete")
        ADD = "ADD", _("add")

    type = models.CharField(
        max_length=10,
        choices=ChangeType.choices,
    )
    field = models.CharField(max_length=255)
    item_id = models.CharField(max_length=255, null=True)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    applied = models.BooleanField(default=False)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["field"]),
            models.Index(fields=["type"]),
            models.Index(fields=["applied"]),
        ]


class DeploymentChange(BaseDeploymentChange):
    ID_PREFIX = "chg_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class ChangeField(models.TextChoices):
        SOURCE = "source", _("source")
        GIT_SOURCE = "git_source", _("git_source")
        BUILDER = "builder", _("builder")
        COMMAND = "command", _("command")
        HEALTHCHECK = "healthcheck", _("healthcheck")
        VOLUMES = "volumes", _("volumes")
        ENV_VARIABLES = "env_variables", _("env variables")
        URLS = "urls", _("urls")
        PORTS = "ports", _("ports")
        RESOURCE_LIMITS = "resource_limits", _("resource limits")
        CONFIGS = "configs", _("configs")

    field = models.CharField(max_length=255, choices=ChangeField.choices)
    service = models.ForeignKey(
        to=Service, on_delete=models.CASCADE, related_name="changes"
    )
    deployment = models.ForeignKey(
        to=Deployment, on_delete=models.CASCADE, related_name="changes", null=True
    )

    def __str__(self):
        return (
            f"DockerDeploymentChange("
            f"\n\ttype={self.type},"
            f"\n\tfield={repr(self.field)},"
            f"\n\titem_id={repr(self.item_id)},"
            f"\n\told_value={repr(self.old_value)},"
            f"\n\tnew_value={repr(self.new_value)},"
            f"\n\tapplied={repr(self.applied)}"
            f"\n)"
        )


class Log(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    service_id = models.CharField(null=True)
    deployment_id = models.CharField(null=True)
    time = models.DateTimeField()

    class Meta:
        abstract = True


class HttpLog(Log):
    class RequestMethod(models.TextChoices):
        GET = "GET", _("GET")
        POST = "POST", _("POST")
        PUT = "PUT", _("PUT")
        DELETE = "DELETE", _("DELETE")
        PATCH = "PATCH", _("PATCH")
        OPTIONS = "OPTIONS", _("OPTIONS")
        HEAD = "HEAD", _("HEAD")

    class RequestProtocols(models.TextChoices):
        HTTP_1_0 = "HTTP/1.0", _("HTTP/1.0")
        HTTP_1_1 = "HTTP/1.1", _("HTTP/1.1")
        HTTP_2 = "HTTP/2.0", _("HTTP/2.0")
        HTTP_3 = "HTTP/3.0", _("HTTP/3.0")

    request_method = models.CharField(
        max_length=7,
        choices=RequestMethod.choices,
    )
    status = models.PositiveIntegerField()
    request_duration_ns = models.BigIntegerField()
    request_headers = models.JSONField()
    response_headers = models.JSONField()
    request_protocol = models.CharField(
        max_length=10,
        choices=RequestProtocols.choices,
        default=RequestProtocols.HTTP_1_1,
    )
    request_host = models.URLField(max_length=1000)
    request_path = models.CharField(max_length=2000)
    request_query = models.CharField(max_length=2000, null=True, blank=True)
    request_ip = models.GenericIPAddressField()
    request_id = models.CharField(null=True, max_length=255)
    request_user_agent = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["deployment_id"]),
            models.Index(fields=["service_id"]),
            models.Index(fields=["request_method"]),
            models.Index(fields=["status"]),
            models.Index(fields=["request_host"]),
            models.Index(fields=["request_path"]),
            models.Index(fields=["time"]),
            models.Index(fields=["request_user_agent"]),
            models.Index(fields=["request_ip"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["request_query"]),
        ]
        ordering = ("-time",)


class Environment(TimestampedModel):
    services: Manager[Service]
    variables = Manager["SharedEnvVariable"]
    PRODUCTION_ENV = "production"

    ID_PREFIX = "project_env_"
    id = ShortUUIDField(
        length=15, max_length=255, unique=True, prefix=ID_PREFIX, primary_key=True
    )

    name = models.SlugField(max_length=255)
    project = models.ForeignKey(
        to=Project, on_delete=models.CASCADE, related_name="environments"
    )
    is_preview = models.BooleanField(default=False)

    def __str__(self):
        return f"Environment(project={self.project.slug}, name={self.name})"

    @property
    def workflow_id(self) -> str:
        return f"create-env-{self.project_id}-{self.id}"

    @property
    def archive_workflow_id(self) -> str:
        return f"archive-env-{self.project_id}-{self.id}"

    @property
    def is_production(self):
        return self.name == "production"  # production is a reserved name

    class Meta:
        indexes = [models.Index(fields=["name"])]
        unique_together = ["name", "project"]
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(name="production"),
                name="unique_production_per_project",
            )
        ]


class SharedEnvVariable(BaseEnvVariable):
    ID_PREFIX = "env_prj_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    environment = models.ForeignKey(
        to=Environment, on_delete=models.CASCADE, related_name="variables"
    )

    class Meta:
        unique_together = ["key", "environment"]
