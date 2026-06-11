from django.db import models
from shortuuid.django_fields import ShortUUIDField


# Create your models here.
class License(models.Model):
    data = models.TextField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)


class InstanceSettings(models.Model):
    id = ShortUUIDField(  # type: ignore
        length=32,
        max_length=255,
        primary_key=True,
        prefix="ist_",
    )
