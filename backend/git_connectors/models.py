# type: ignore
from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils import timezone
from zane_api.utils import cache_result

import jwt
from datetime import timedelta
import requests

from zane_api.models.base import TimestampedModel
import hashlib
import hmac

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


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

    def __str__(self):
        return f"GitRepository(url={self.url}, private={self.private})"

    class Meta:
        indexes = [
            models.Index(
                models.Func(models.F("owner"), function="UPPER"),
                name="owner_istartswith_idx",
            ),
            models.Index(
                models.Func(models.F("repo"), function="UPPER"),
                name="repo_istartswith_idx",
            ),
        ]


class GitHubApp(TimestampedModel):
    ID_PREFIX = "gh_app_"
    id = ShortUUIDField(
        length=14,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    name = models.CharField(max_length=255)
    installation_id = models.PositiveIntegerField(null=True)
    app_url = models.URLField(max_length=255, blank=False)
    client_id = models.CharField(max_length=255, blank=False)
    app_id = models.PositiveIntegerField(unique=True)
    client_secret = models.TextField(blank=False)
    webhook_secret = models.TextField(blank=False)
    private_key = models.TextField(blank=False)
    repositories = models.ManyToManyField(to=GitRepository, related_name="githubapps")

    if TYPE_CHECKING:
        repositories: RelatedManager["GitRepository"]

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
    def get_access_token(self) -> str:
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

    def get_authenticated_repository_url(self, repo_url: str):
        access_token = self.get_access_token()
        return (
            f"https://x-access-token:{access_token}@{repo_url.replace('https://', '')}"
        )

    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify that the payload was sent from GitHub by validating SHA256.

        Args:
            payload_body: original request body to verify
            signature_header: header received from GitHub (x-hub-signature-256)
        """
        hash_object = hmac.new(
            self.webhook_secret.encode("utf-8"),
            msg=payload_body,
            digestmod=hashlib.sha256,
        )
        expected_signature = "sha256=" + hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)

    def add_repositories(self, repos: list[GitRepository]):
        existing_repos = self.repositories.filter(
            url__in=[repo.url for repo in repos]
        ).values_list("url", flat=True)
        new_repos = [repo for repo in repos if repo.url not in existing_repos]

        self.repositories.add(*GitRepository.objects.bulk_create(new_repos))

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
