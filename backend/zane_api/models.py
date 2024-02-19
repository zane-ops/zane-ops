from datetime import datetime
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class TimestampedModel(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Project(TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, unique=True)
    archived = models.BooleanField(default=False)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.slug:
            self.slug = slugify(self.name.strip())
        super().save()

    def __str__(self):
        return self.name


class BaseService(TimestampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    archived = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    base_domain = models.URLField(max_length=1000, null=True, blank=True)
    project = models.ForeignKey(
        to=Project,
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True
        unique_together = (
            "slug",
            "project",
        )

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.slug:
            self.slug = slugify(self.name.strip())
        super().save()

    def __str__(self):
        return self.name


class DockerRegistryService(BaseService):
    base_docker_image = models.CharField(max_length=510)
    docker_credentials_email = models.CharField(max_length=255, null=True, blank=True)
    docker_credentials_password = models.CharField(
        max_length=255, null=True, blank=True
    )

    def __str__(self):
        return self.name


class GitRepositoryService(BaseService):
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

    def __str__(self):
        return self.name
