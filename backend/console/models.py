from django.db import models
from zane_api.models.base import TimestampedModel
from django.conf import settings
from typing import Self
from django.core.validators import MinValueValidator


class PasswordResetToken(TimestampedModel):
    value = models.CharField(
        max_length=255,
        unique=True,
    )
    expires_at = models.DateTimeField()
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )


SINGLETON_ID = 1


class SystemSettings(TimestampedModel):
    # CRON schedules
    docker_system_prune_cron_schedule = models.CharField(
        default="0 */4 * * *"
    )  # default: every 4 hours
    metrics_cleanup_cron_schedule = models.CharField(
        default="0 0 * * *"
    )  # default: every day at midnight

    # retention policies, `null` mean "always retained"
    http_log_retention_days = models.PositiveIntegerField(
        null=True, validators=[MinValueValidator(1)]
    )
    build_cache_max_age_days = models.PositiveIntegerField(
        null=True, validators=[MinValueValidator(1)]
    )
    build_cache_max_use_space_bytes = models.PositiveIntegerField(
        null=True, validators=[MinValueValidator(1)]
    )
    # TODO:
    # You delete build cache like this
    # docker buildx prune --force --all --filter until=<days*24>h --max-used-space <bytes>

    # Docker system prune config
    prune_images = models.BooleanField(default=True)
    prune_containers = models.BooleanField(default=True)
    prune_volumes = models.BooleanField(default=True)
    prune_networks = models.BooleanField(default=True)

    @classmethod
    def get(cls) -> Self:
        return cls.objects.filter(pk=SINGLETON_ID).first() or cls()

    @classmethod
    async def aget(cls) -> Self:
        return (await cls.objects.filter(pk=SINGLETON_ID).afirst()) or cls()

    def save(self, *args, **kwargs):
        self.pk = SINGLETON_ID
        super().save(*args, **kwargs)

    class Meta:  # type: ignore
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=SINGLETON_ID),
                name="server_settings_singleton_id",
            ),
        ]
