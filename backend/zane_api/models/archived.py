from django.conf import settings
from django.db import models


class TimestampArchivedModel(models.Model):
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class ArchivedProject(TimestampArchivedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    slug = models.SlugField(max_length=255, blank=True)

    def __str__(self):
        return f"ArchivedProject({self.slug})"

    class Meta:
        indexes = [models.Index(fields=["slug"])]
