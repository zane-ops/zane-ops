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
    project = models.ForeignKey(to=Project, on_delete=models.CASCADE)
    volumes = models.ManyToManyField(to="Volume")
    ports = models.ManyToManyField(to="PortConfiguration")
    urls = models.ManyToManyField(to=URL)
    healthcheck = models.ForeignKey(
        to=HealthCheck, null=True, on_delete=models.SET_NULL
    )
    network_alias = models.CharField(max_length=300, null=True, unique=True)
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


class DockerEnvVariable(BaseEnvVariable):
    ID_PREFIX = "env_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    service = models.ForeignKey(
        to="DockerRegistryService",
        on_delete=models.CASCADE,
        related_name="env_variables",
    )

    def __str__(self):
        return f"DockerEnvVariable({self.key})"

    class Meta:
        unique_together = ["key", "service"]


class DockerRegistryService(BaseService):
    deployments: Manager["DockerDeployment"]
    changes: Manager["DockerDeploymentChange"]
    ports: Manager["PortConfiguration"]
    env_variables: Manager[DockerEnvVariable]
    urls: Manager[URL]
    volumes: Manager["Volume"]
    configs: Manager["Config"]
    project_id: str

    ID_PREFIX = "srv_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    image = models.CharField(max_length=510, null=True)
    command = models.TextField(null=True, blank=True)
    credentials = models.JSONField(
        max_length=255,
        null=True,
    )

    environment: models.ForeignKey["Environment"] = models.ForeignKey(
        to="Environment",
        on_delete=models.CASCADE,
        related_name="services",
    )

    def __str__(self):
        return f"DockerRegistryService({self.slug})"

    class Meta:
        unique_together = ("slug", "project", "environment")

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
        return [
            {
                "key": "ZANE",
                "value": "true",
                "comment": "Is the service deployed on zaneops?",
            },
            {
                "key": "ZANE_PRIVATE_DOMAIN",
                "value": f"{self.network_alias}.{settings.ZANE_INTERNAL_DOMAIN}",
                "comment": "The domain used to reach this service on the same project",
            },
            {
                "key": "ZANE_DEPLOYMENT_TYPE",
                "value": "docker",
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
                status=DockerDeployment.DeploymentStatus.QUEUED,
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

    def apply_pending_changes(self, deployment: "DockerDeployment"):
        for change in self.unapplied_changes:
            match change.field:
                case DockerDeploymentChange.ChangeField.COMMAND:
                    setattr(self, change.field, change.new_value)
                case DockerDeploymentChange.ChangeField.SOURCE:
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
                case DockerDeploymentChange.ChangeField.RESOURCE_LIMITS:
                    if change.new_value is None:
                        self.resource_limits = None
                        continue
                    self.resource_limits = {
                        "cpus": change.new_value.get("cpus"),
                        "memory": change.new_value.get("memory"),
                    }
                case DockerDeploymentChange.ChangeField.HEALTHCHECK:
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
                case DockerDeploymentChange.ChangeField.VOLUMES:
                    if change.type == DockerDeploymentChange.ChangeType.ADD:
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
                    if change.type == DockerDeploymentChange.ChangeType.DELETE:
                        self.volumes.get(id=change.item_id).delete()
                    if change.type == DockerDeploymentChange.ChangeType.UPDATE:
                        config = self.volumes.get(id=change.item_id)
                        config.host_path = change.new_value.get("host_path")
                        config.container_path = change.new_value.get("container_path")
                        config.mode = change.new_value.get("mode")
                        config.name = change.new_value.get("name", config.name)
                        config.save()
                case DockerDeploymentChange.ChangeField.CONFIGS:
                    if change.type == DockerDeploymentChange.ChangeType.ADD:
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
                    if change.type == DockerDeploymentChange.ChangeType.DELETE:
                        self.configs.get(id=change.item_id).delete()
                    if change.type == DockerDeploymentChange.ChangeType.UPDATE:
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
                case DockerDeploymentChange.ChangeField.ENV_VARIABLES:
                    if change.type == DockerDeploymentChange.ChangeType.ADD:
                        DockerEnvVariable.objects.create(
                            key=change.new_value.get("key"),
                            value=change.new_value.get("value"),
                            service=self,
                        )
                    if change.type == DockerDeploymentChange.ChangeType.DELETE:
                        self.env_variables.get(id=change.item_id).delete()
                    if change.type == DockerDeploymentChange.ChangeType.UPDATE:
                        env = self.env_variables.get(id=change.item_id)
                        env.key = change.new_value.get("key")
                        env.value = change.new_value.get("value")
                        env.save()
                case DockerDeploymentChange.ChangeField.URLS:
                    if change.type == DockerDeploymentChange.ChangeType.ADD:
                        self.urls.add(
                            URL.objects.create(
                                domain=change.new_value.get("domain"),
                                base_path=change.new_value.get("base_path"),
                                strip_prefix=change.new_value.get("strip_prefix"),
                                redirect_to=change.new_value.get("redirect_to"),
                                associated_port=change.new_value.get("associated_port"),
                            )
                        )
                    if change.type == DockerDeploymentChange.ChangeType.DELETE:
                        self.urls.get(id=change.item_id).delete()
                    if change.type == DockerDeploymentChange.ChangeType.UPDATE:
                        url = self.urls.get(id=change.item_id)
                        url.domain = change.new_value.get("domain")
                        url.base_path = change.new_value.get("base_path")
                        url.strip_prefix = change.new_value.get("strip_prefix")
                        url.redirect_to = change.new_value.get("redirect_to")
                        url.associated_port = change.new_value.get("associated_port")
                        url.save()
                case DockerDeploymentChange.ChangeField.PORTS:
                    if change.type == DockerDeploymentChange.ChangeType.ADD:
                        self.ports.add(
                            PortConfiguration.objects.create(
                                host=change.new_value.get("host"),
                                forwarded=change.new_value.get("forwarded"),
                            )
                        )

                    if change.type == DockerDeploymentChange.ChangeType.DELETE:
                        self.ports.get(id=change.item_id).delete()
                    if change.type == DockerDeploymentChange.ChangeType.UPDATE:
                        port = self.ports.get(id=change.item_id)
                        port.host = change.new_value.get("host")
                        port.forwarded = change.new_value.get("forwarded")
                        port.save()

        self.unapplied_changes.update(applied=True, deployment=deployment)
        self.save()
        self.refresh_from_db()

    def add_change(self, change: "DockerDeploymentChange"):
        change.service = self
        match change.field:
            case (
                DockerDeploymentChange.ChangeField.SOURCE
                | DockerDeploymentChange.ChangeField.COMMAND
                | DockerDeploymentChange.ChangeField.HEALTHCHECK
                | DockerDeploymentChange.ChangeField.RESOURCE_LIMITS
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

    service = models.ForeignKey(to=DockerRegistryService, on_delete=models.CASCADE)
    deployment = models.ForeignKey["DockerDeployment"](
        to="DockerDeployment", on_delete=models.CASCADE
    )

    class Meta:
        indexes = [models.Index(fields=["created_at"])]


class GitRepositoryService(BaseService):
    ID_PREFIX = "srv_git_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
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

    @property
    def unprefixed_id(self):
        return self.id.replace(self.ID_PREFIX, "") if self.id is not None else None


class GitEnvVariable(BaseEnvVariable):
    service = models.ForeignKey(
        to="GitRepositoryService",
        on_delete=models.CASCADE,
        related_name="env_variables",
    )

    def __str__(self):
        return f"GitEnvVariable({self.key})"


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
    deployment: models.ForeignKey["DockerDeployment"] = models.ForeignKey(
        to="DockerDeployment",
        on_delete=models.CASCADE,
        related_name="urls",
    )

    @classmethod
    def generate_for_deployment(
        cls,
        deployment: "DockerDeployment",
        port: int,
        service: "DockerRegistryService",
    ):
        return cls.objects.create(
            domain=f"{service.project.slug}-{service.slug}-{deployment.hash.replace('_', '-')}-{generate_random_chars(10)}.{settings.ROOT_DOMAIN}".lower(),
            port=port,
            deployment=deployment,
        )

    class Meta:
        indexes = [models.Index(fields=["domain"])]


class BaseDeployment(models.Model):
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        abstract = True


class DockerDeployment(BaseDeployment):
    HASH_PREFIX = "dpl_dkr_"
    urls = Manager["DeploymentURL"]
    hash = ShortUUIDField(length=11, max_length=255, unique=True, prefix=HASH_PREFIX)

    is_redeploy_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True)

    class DeploymentStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        CANCELLED = "CANCELLED", _("Cancelled")
        CANCELLING = "CANCELLING", _("Cancelling")
        FAILED = "FAILED", _("Failed")
        PREPARING = "PREPARING", _("Preparing")
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
        to=DockerRegistryService, on_delete=models.CASCADE, related_name="deployments"
    )
    service_snapshot = models.JSONField(null=True)
    commit_message = models.TextField(default="update service")

    @classmethod
    def get_next_deployment_slot(
        cls,
        latest_production_deployment: Optional["DockerDeployment"],
    ) -> str:
        if (
            latest_production_deployment is not None
            and latest_production_deployment.slot
            == DockerDeployment.DeploymentSlot.BLUE
            and latest_production_deployment.status
            != DockerDeployment.DeploymentStatus.FAILED
            # 👆🏽 technically this can only be true for the initial deployment
            # for the next deployments, when they fail, they will not be promoted to production
        ):
            return DockerDeployment.DeploymentSlot.GREEN
        return DockerDeployment.DeploymentSlot.BLUE

    @property
    def workflow_id(self):
        return f"deploy-{self.service.id}-{self.service.project_id}"

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
            aliases = self.service.network_aliases + [
                f"{self.service.network_alias}.{self.slot.lower()}.{settings.ZANE_INTERNAL_DOMAIN}",
            ]
        return aliases

    @property
    def network_alias(self):
        return f"{self.service.network_alias}.{self.service.environment.name}.{self.slot.lower()}.{settings.ZANE_INTERNAL_DOMAIN}"

    class Meta:
        ordering = ("-queued_at",)
        indexes = [
            models.Index(fields=["status"]),
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


class DockerDeploymentChange(BaseDeploymentChange):
    ID_PREFIX = "chg_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class ChangeField(models.TextChoices):
        SOURCE = "source", _("source")
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
        to=DockerRegistryService, on_delete=models.CASCADE, related_name="changes"
    )
    deployment = models.ForeignKey(
        to=DockerDeployment, on_delete=models.CASCADE, related_name="changes", null=True
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


class GitDeployment(BaseDeployment):
    HASH_PREFIX = "dpl_git_"
    hash = ShortUUIDField(length=11, max_length=255, unique=True, prefix=HASH_PREFIX)

    is_redeploy_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True)

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

    class DeploymentStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        PREPARING = "PREPARING", _("Preparing")
        FAILED = "FAILED", _("Failed")
        REMOVED = "REMOVED", _("Removed")
        STARTING = "STARTING", _("Starting")
        RESTARTING = "RESTARTING", _("Restarting")
        BUILDING = "BUILDING", _("Building")
        CANCELLED = "CANCELLED", _("Cancelled")
        HEALTHY = "HEALTHY", _("Healthy")
        UNHEALTHY = "UNHEALTHY", _("UnHealthy")
        OFFLINE = "OFFLINE", _("Offline")
        SLEEPING = "SLEEPING", _("Sleeping")  # preview deploys

    status = models.CharField(
        max_length=10,
        choices=DeploymentStatus.choices,
        default=DeploymentStatus.QUEUED,
    )
    status_reason = models.CharField(max_length=255, null=True)

    class DeploymentEnvironment(models.TextChoices):
        PRODUCTION = "PRODUCTION", _("Production")
        PREVIEW = "PREVIEW", _("Preview")

    deployment_environment = models.CharField(
        max_length=10,
        choices=DeploymentEnvironment.choices,
        default=DeploymentEnvironment.PREVIEW,
    )
    is_current_production = models.BooleanField(default=False)

    commit_hash = models.CharField(
        max_length=40
    )  # Typical length of a Git commit hash, but we will use the short version
    commit_message = models.TextField(blank=True)
    build_duration_in_ms = models.PositiveIntegerField(null=True)
    branch = models.CharField(max_length=255)
    service = models.ForeignKey(to=GitRepositoryService, on_delete=models.CASCADE)
    commit_author_username = models.CharField(max_length=255)
    commit_author_avatar_url = models.URLField(null=True)

    def __str__(self):
        return f"GitDeployment(branch={self.branch} - commit_ha={self.commit_hash[:7]} - status={self.build_status})"

    @property
    def unprefixed_hash(self):
        return None if self.hash is None else self.hash.replace(self.HASH_PREFIX, "")

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_current_production"]),
        ]


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
    ID_PREFIX = "project_env_"
    PRODUCTION_ENV = "production"
    services: Manager[DockerRegistryService]
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
