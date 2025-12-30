from typing import TYPE_CHECKING
from django.db import models

from zane_api.models import TimestampedModel, Project, Environment, BaseEnvVariable
from shortuuid.django_fields import ShortUUIDField

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class ComposeStack(TimestampedModel):
    """Represents a docker-compose stack (file-based, NOT container-based)"""

    ID_PREFIX = "compose_stk_"
    project_id: str
    environment_id: str

    if TYPE_CHECKING:
        changes: RelatedManager["ComposeStackChange"]

    id = ShortUUIDField(
        length=8,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )  # type: ignore
    slug = models.SlugField(max_length=38)

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="compose_stacks",
    )
    environment = models.ForeignKey(
        Environment,
        on_delete=models.CASCADE,
        related_name="compose_stacks",
    )
    deploy_token = models.CharField(max_length=35, null=True, unique=True)

    # Compose content
    user_compose_content = models.TextField(
        help_text="Original YAML from user",
        null=True,
        blank=False,
    )
    computed_compose_content = models.TextField(
        help_text="Processed YAML",
        null=True,
        blank=False,
    )

    # Dict mapping service names to list of route configs:
    #         {
    #             "web": [
    #                 {
    #                     "domain": "example.com",
    #                     "base_path": "/",
    #                     "strip_prefix": False,
    #                     "port": 80,
    #                 }
    #             ]
    #         }
    urls = models.JSONField(null=True)

    class Meta:  # type: ignore
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "project", "environment"],
                name="unique_compose_slug_per_env_and_project",
            ),
        ]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["deploy_token"]),
        ]

    @property
    def name(self):
        return f"zn-{self.slug}-{self.id.replace(self.ID_PREFIX, '')}".lower()

    @property
    def unapplied_changes(self):
        return self.changes.filter(applied=False)


class ComposeStackDeployment(TimestampedModel):
    """Tracks deployments of compose stacks"""

    HASH_PREFIX = "stk_dpl_"
    hash = ShortUUIDField(
        length=11, max_length=255, primary_key=True, prefix=HASH_PREFIX
    )  # type: ignore
    stack = models.ForeignKey(
        ComposeStack, on_delete=models.CASCADE, related_name="deployments"
    )

    class DeploymentStatus(models.TextChoices):
        QUEUED = "QUEUED"
        CANCELLED = "CANCELLED"
        FAILED = "FAILED"
        DEPLOYING = "DEPLOYING"
        HEALTHY = "HEALTHY"
        UNHEALTHY = "UNHEALTHY"
        REMOVED = "REMOVED"

    status = models.CharField(
        max_length=10, choices=DeploymentStatus.choices, default=DeploymentStatus.QUEUED
    )
    status_reason = models.TextField(null=True, blank=True)

    # Per-service status (JSON)
    service_statuses = models.JSONField(default=dict)
    # Example:
    # {
    #     "web": {
    #         "status": "running",
    #         "desired_replicas": 2,
    #         "running_replicas": 2,
    #         "updated_at": "2025-12-26T10:30:00Z"
    #     },
    #     "db": {...}
    # }

    # Snapshot and metadata
    stack_snapshot = models.JSONField(null=True)
    commit_message = models.TextField(default="update stack")

    # Timing
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    @property
    def workflow_id(self):
        return f"deploy-compose-{self.stack.id}"


class ComposeStackEnvOverride(BaseEnvVariable):
    """Environment variable overrides at stack level"""

    ID_PREFIX = "stk_env_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )  # type: ignore
    stack = models.ForeignKey(
        ComposeStack,
        on_delete=models.CASCADE,
        related_name="env_overrides",
    )

    class Meta:  # type: ignore
        unique_together = ["key", "stack"]


class ComposeStackChange(TimestampedModel):
    """Tracks unapplied changes to compose stacks"""

    ID_PREFIX = "stk_chg_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )  # type: ignore

    class ChangeField(models.TextChoices):
        COMPOSE_CONTENT = "compose_content"
        ENV_OVERRIDES = "env_overrides"
        URLS = "urls"

    class ChangeType(models.TextChoices):
        ADD = "ADD"
        UPDATE = "UPDATE"
        DELETE = "DELETE"

    stack = models.ForeignKey(
        ComposeStack,
        on_delete=models.CASCADE,
        related_name="changes",
    )
    deployment = models.ForeignKey(
        ComposeStackDeployment,
        on_delete=models.CASCADE,
        null=True,
        related_name="changes",
    )
    field = models.CharField(max_length=255, choices=ChangeField.choices)
    type = models.CharField(max_length=10, choices=ChangeType.choices)
    item_id = models.CharField(max_length=255, null=True)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
