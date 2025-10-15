from django.db import models
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField


# Create your models here.
class S3Credentials(TimestampedModel):
    ID_PREFIX = "s3_"
    id = ShortUUIDField(primary_key=True, prefix=ID_PREFIX, length=11)  # type: ignore[arg-type]
    name = models.CharField(max_length=255)
    bucket = models.CharField(max_length=255)
    region = models.CharField(max_length=100, default="us-east-1")
    access_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    endpoint_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return f"S3({self.bucket}@{self.region})"
