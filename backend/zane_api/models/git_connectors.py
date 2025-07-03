# type: ignore
from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils import timezone
from ..utils import (
    cache_result,
)

import jwt
from datetime import timedelta
import requests

from .base import TimestampedModel


class GitRepository(TimestampedModel):
    ID_PREFIX = "repo_"
    id = ShortUUIDField(
        length=14,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    owner = models.SlugField(max_length=255)
    repo = models.SlugField(max_length=255)
    url = models.URLField(unique=True)
    private = models.BooleanField()


class GithubApp(TimestampedModel):
    ID_PREFIX = "gh_app_"
    id = ShortUUIDField(
        length=14,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    name = models.CharField(max_length=255)
    installation_id = models.CharField(max_length=255, null=True)
    app_url = models.URLField(max_length=255, blank=False)
    client_id = models.CharField(max_length=255, blank=False)
    app_id = models.PositiveIntegerField(unique=True)
    client_secret = models.TextField(blank=False)
    webhook_secret = models.TextField(blank=False)
    private_key = models.TextField(blank=False)
    repositories = models.ManyToManyField(to=GitRepository)

    def __str__(self):
        return f"GithubApp(id={self.id})"

    def _generate_jwt(self) -> str:
        now = int(timezone.now().timestamp())
        payload = {
            # issued at time, 60 seconds in the past to allow for clock drift
            "iat": now - 60,
            # JWT expiration time (10 minute maximum)
            "exp": now + timedelta(minutes=10).seconds,
            "iss": self.client_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    @cache_result(timeout=timedelta(minutes=59))
    def get_installation_token(self) -> str:
        assert self.is_installed

        jwt = self._generate_jwt()
        response = requests.post(
            f"https://api.github.com/app/installations/{self.installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        return response.json()["token"]

    @property
    def is_installed(self):
        return (
            bool(self.installation_id)
            and bool(self.client_id)
            and bool(self.client_secret)
            and bool(self.webhook_secret)
            and bool(self.private_key)
        )


class GitlabApp(TimestampedModel):
    id = ShortUUIDField(
        length=14,
        max_length=255,
        primary_key=True,
        prefix="gl_app_",
    )
    slug = models.SlugField(max_length=255)
    gitlab_url = models.URLField(default="https://gitlab.com")
    app_id = models.CharField(max_length=255, null=True)
    redirect_uri = models.URLField(max_length=255, null=True)
    secret = models.TextField(null=True)
    access_token = models.TextField(null=True)
    refresh_token = models.TextField(null=True)
    group_name = models.CharField(max_length=2000, null=True)
    expires_at = models.PositiveBigIntegerField(null=True)
    repositories = models.ManyToManyField(to=GitRepository)
