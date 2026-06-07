from django.db import models
from zane_api.models.base import TimestampedModel
from django.conf import settings


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
