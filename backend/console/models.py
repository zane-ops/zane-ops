from django.db import models
from zane_api.models.base import TimestampedModel
from django.conf import settings
from typing import Self
from django.core.validators import MinValueValidator

# from shortuuid.django_fields import ShortUUIDField
from zane_api.utils import convert_value_to_bytes


# class CustomProxyConfig(TimestampedModel):
#     """
#     A custom Caddyfile snippet added by the instance owner to the ZaneOps proxy,
#     it is adapted to JSON & installed in the proxy as a single route
#     identified by `{CADDY_ID_PREFIX}{id}`.
#     """

#     ID_PREFIX = "prx_cfg_"
#     CADDY_ID_PREFIX = "zane-custom-config-"

#     id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)  # type: ignore
#     slug = models.SlugField(max_length=255, unique=True)
#     contents = models.TextField()
#     enabled = models.BooleanField(default=True)

#     @property
#     def caddy_route_id(self) -> str:
#         return f"{self.CADDY_ID_PREFIX}{self.id}"

#     class Meta:  # type: ignore
#         ordering = ("-updated_at",)

#     def __str__(self):
#         return f"CustomProxyConfig({self.slug})"


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
    app_data_cleanup_cron_schedule = models.CharField(
        default="0 0 * * *"
    )  # default: every day at midnight

    # retention policies, `null` mean "always retained"
    http_log_retention_days = models.PositiveIntegerField(
        null=True, validators=[MinValueValidator(1)]
    )
    build_cache_max_age_days = models.PositiveIntegerField(
        null=True,
        default=30,
        validators=[MinValueValidator(1)],
    )
    build_cache_max_use_space_bytes = models.PositiveBigIntegerField(
        null=True,
        default=convert_value_to_bytes(5, "GIGABYTES"),
        validators=[MinValueValidator(1)],
    )

    # Docker system prune config
    prune_images = models.BooleanField(default=True)
    prune_containers = models.BooleanField(default=True)
    prune_volumes = models.BooleanField(default=True)
    prune_networks = models.BooleanField(default=True)

    @classmethod
    def get_or_create(cls) -> Self:
        object = cls.objects.filter(pk=SINGLETON_ID).first()
        if not object:
            object = cls()
            object.save()
        return object

    @classmethod
    async def aget_or_create(cls) -> Self:
        object = await cls.objects.filter(pk=SINGLETON_ID).afirst()
        if not object:
            object = cls()
            await object.asave()
        return object

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
