from django.db import models
from zane_api.models import TimestampedModel


class SSHKey(TimestampedModel):
    DEFAULT = "default"
    user = models.CharField(max_length=255, blank=False)
    key = models.TextField(unique=True, blank=False)
    name = models.CharField(max_length=255, blank=False)
