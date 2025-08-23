# type: ignore
from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils import timezone
from zane_api.utils import (
    cache_result,
    add_suffix_if_missing,
    find_item_in_sequence,
)
from typing import Optional
import asyncio
import jwt
from datetime import timedelta
import requests

from zane_api.models.base import TimestampedModel
import hashlib
import hmac
from django.conf import settings

from typing import TYPE_CHECKING
from asgiref.sync import sync_to_async
from urllib.parse import urlencode, urlparse
import re
import secrets

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
    path = models.CharField(max_length=2000, blank=True)
    url = models.URLField(unique=True)
    private = models.BooleanField()

    def __str__(self):
        return f"GitRepository(url={self.url}, private={self.private})"

    class Meta:
        indexes = []


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

    class Meta:
        indexes = [models.Index(fields=["installation_id"])]

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
        return f"https://x-access-token:{access_token}@{re.sub(r'https?://', '', repo_url)}"

    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify that the payload was sent from GitHub by validating SHA256.

        Args:
            payload_body: original request body to verify
            signature_header: header value received from GitHub (x-hub-signature-256)
        """
        hash_object = hmac.new(
            self.webhook_secret.encode("utf-8"),
            msg=payload_body,
            digestmod=hashlib.sha256,
        )
        expected_signature = "sha256=" + hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)

    def add_repositories(self, repos: list[GitRepository]):
        existing_repos = GitRepository.objects.filter(
            url__in=[repo.url for repo in repos]
        ).values_list("url", flat=True)
        new_repos = [repo for repo in repos if repo.url not in existing_repos]
        GitRepository.objects.bulk_create(new_repos)

        repos_to_add = GitRepository.objects.filter(
            url__in=[repo.url for repo in repos]
        )

        self.repositories.add(*repos_to_add)

    @property
    def is_installed(self):
        return (
            bool(self.installation_id)
            and bool(self.client_id)
            and bool(self.client_secret)
            and bool(self.webhook_secret)
            and bool(self.private_key)
        )


def get_default_redirect_uri():
    return f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup"


def get_default_webhook_secret():
    return secrets.token_hex()


class GitlabApp(TimestampedModel):
    ID_PREFIX = "gl_app_"
    SETUP_STATE_CACHE_PREFIX = "gitlab-setup"
    UPDATE_STATE_CACHE_PREFIX = "gitlab-update"
    id = ShortUUIDField(
        length=14,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    name = models.CharField(max_length=255, blank=False)
    gitlab_url = models.URLField(default="https://gitlab.com")
    redirect_uri = models.URLField(default=get_default_redirect_uri)
    webhook_secret = models.CharField(
        max_length=65,
        default=get_default_webhook_secret,
        unique=True,
    )
    app_id = models.CharField(max_length=255, blank=False)
    secret = models.TextField(blank=False)
    refresh_token = models.TextField(blank=False)
    repositories = models.ManyToManyField(to=GitRepository, related_name="gitlabapps")

    def __str__(self):
        return f"GitlabApp(app_id={self.app_id},secret={self.secret})"

    @property
    def is_installed(self):
        return bool(self.refresh_token)

    def fetch_all_repositories_from_gitlab(self):
        PAGE_SIZE = 100  # the max page size GitLab can accept

        base_url = f"{self.gitlab_url}/api/v4/projects"

        params = {
            "per_page": PAGE_SIZE,
            "pagination": "keyset",
            "order_by": "id",
            "membership": "true",
            "sort": "desc",
            "min_access_level": 40,  # Maintainer
        }

        cursor: Optional[str] = None

        has_fetched_all_pages = False
        git_repositories: list[GitRepository] = []
        repositories_to_create: list[GitRepository] = []

        while not has_fetched_all_pages:
            access_token = GitlabApp.ensure_fresh_access_token(self)
            querystring = dict(params)
            if cursor is not None:
                querystring["id_before"] = cursor

            response = requests.get(
                base_url + "?" + urlencode(querystring, doseq=True),
                headers=dict(Authorization=f"Bearer {access_token}"),
            )

            response.raise_for_status()
            found_repositories: list[dict[str, int | str | bool]] = response.json()

            repositories_urls = [
                add_suffix_if_missing(repo["http_url_to_repo"], ".git")
                for repo in found_repositories
            ]

            existing_repos = GitRepository.objects.filter(url__in=repositories_urls)

            git_repositories.extend(existing_repos)
            existing_repos_urls = [repo.url for repo in existing_repos]
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            # Run this asynchronously so that we can run these functions in parallel
            loop.run_until_complete(
                self._create_or_edit_project_webhooks(found_repositories)
            )

            for repository in found_repositories:
                repo_url = add_suffix_if_missing(repository["http_url_to_repo"], ".git")
                if repo_url not in existing_repos_urls:
                    repositories_to_create.append(
                        GitRepository(
                            url=repo_url,
                            path=repository["path_with_namespace"],
                            private=repository["visibility"] == "private",
                        )
                    )

            if len(found_repositories) < PAGE_SIZE:
                has_fetched_all_pages = True
                break

            if len(found_repositories) > 0:
                last_repository = found_repositories.pop()
                cursor = last_repository["id"]

        # detach all repositories from this
        self.repositories.remove()

        git_repositories.extend(
            GitRepository.objects.bulk_create(repositories_to_create)
        )

        # Then readd all the repositories needed for this
        self.repositories.add(*git_repositories)

        # cleanup orphan repositories
        GitRepository.objects.filter(
            gitlabapps__isnull=True, githubapps__isnull=True
        ).delete()

    async def _create_or_edit_project_webhooks(self, projects: list[dict[str, int]]):
        async def create_project_webhook_in_executor(project_id: int):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._create_or_edit_project_webhook, project_id
            )

        await asyncio.gather(
            *[create_project_webhook_in_executor(project["id"]) for project in projects]
        )

    def _create_or_edit_project_webhook(self, project_id: int):
        access_token = GitlabApp.ensure_fresh_access_token(self)

        parsed_app_url = urlparse(self.redirect_uri)
        scheme = parsed_app_url.scheme
        domain = parsed_app_url.netloc

        hook_name = f"ZaneOps-{self.id}"
        base_url = f"{self.gitlab_url}/api/v4/projects/{project_id}/hooks"

        request_body = {
            "url": f"{scheme}://{domain}/api/connectors/gitlab/webhook",
            "push_events": True,
            "merge_request_events": True,
            "name": hook_name,
            "enable_ssl_verification": scheme == "https",
            "token": self.webhook_secret,
            "branch_filter_strategy": "all_branches",
        }

        response = requests.get(
            base_url,
            headers=dict(Authorization=f"Bearer {access_token}"),
        )
        response.raise_for_status()

        data: list[dict[str, int | str | bool]] = response.json()
        hook_found = find_item_in_sequence(lambda hook: hook["name"] == hook_name, data)
        if not hook_found:
            response = requests.post(
                base_url,
                json=request_body,
                headers=dict(Authorization=f"Bearer {access_token}"),
            )
            response.raise_for_status()
            return

        response = requests.put(
            base_url + f"/{hook_found['id']}",
            json=request_body,
            headers=dict(Authorization=f"Bearer {access_token}"),
        )
        response.raise_for_status()

        return

    @classmethod
    @cache_result(
        # access tokens on gitlab are valid for only up to 2 hours,
        # so we store it for 1 min less to not use an invalid token
        timeout=timedelta(hours=1, minutes=59)
    )
    def ensure_fresh_access_token(cls, app: "GitlabApp") -> str:
        assert app.is_installed

        response = requests.post(
            f"{app.gitlab_url}/oauth/token",
            data=dict(
                client_id=app.app_id,
                client_secret=app.secret,
                grant_type="refresh_token",
                redirect_uri=app.redirect_uri,
                refresh_token=app.refresh_token,
            ),
        )

        response.raise_for_status()

        data = response.json()

        # update the refresh token
        app.refresh_token = data["refresh_token"]
        app.save()
        return data["access_token"]

    @classmethod
    async def aensure_fresh_access_token(cls, app: "GitlabApp") -> str:
        return await sync_to_async(cls.ensure_fresh_access_token)(app)

    def get_authenticated_repository_url(self, repo_url: str):
        access_token = GitlabApp.ensure_fresh_access_token(self)
        return f"https://oauth2:{access_token}@{re.sub(r'https?://', '', repo_url)}"
