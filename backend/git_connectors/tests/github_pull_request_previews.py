import re
from typing import cast

import responses
from ..serializers.github import GithubWebhookEvent
from zane_api.tests.base import AuthAPITestCase
from .fixtures import (
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
    GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
    GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
    get_github_signed_event_headers,
)

from asgiref.sync import sync_to_async
from rest_framework import status
from zane_api.utils import generate_random_chars
from ..models import GitHubApp
from zane_api.models import GitApp
from django.urls import reverse
from zane_api.models import Environment, PreviewEnvMetadata
from django.utils.text import slugify


class CreatePRPreviewEnvViewTests(AuthAPITestCase):
    def create_and_install_github_app(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"^https://api\.github\.com/app/installations/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json={"token": generate_random_chars(32)},
        )

        github = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        gitapp = GitApp.objects.create(github=github)

        # install app
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return gitapp

    async def acreate_and_install_github_app(self):
        return await sync_to_async(self.create_and_install_github_app)()

    @responses.activate
    def test_open_pull_request_should_create_preview_env(self):
        gitapp = self.create_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)

        self.create_and_deploy_redis_docker_service()
        p, _ = self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)
        preview_meta = cast(PreviewEnvMetadata, preview_env.preview_metadata)
        self.assertIsNotNone(preview_meta)

        pr_data = GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA["pull_request"]

        self.assertEqual(
            f"preview-pr-{pr_data['number']}-{service.slug}",
            preview_env.name,
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(pr_data["head"]["ref"], preview_meta.branch_name)
        repo_url = "https://github.com/" + pr_data["head"]["repo"]["full_name"] + ".git"
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(
            pr_data["html_url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.APPROVED,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            pr_data["number"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            pr_data["title"],
            preview_meta.pr_title,
        )
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_meta.template
        )
        self.assertEqual(service, preview_meta.service)
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(gitapp, preview_meta.git_app)
        self.assertEqual("HEAD", preview_meta.commit_sha)

        self.assertEqual(2, preview_env.services.count())

    def test_close_pull_request_should_delete_preview_env(self):
        self.assertFalse(True)

    def test_do_not_deploy_preview_env_on_fork_prs(self):
        self.assertFalse(True)

    def test_webhook_pr_synchronize_redeploy_service(self):
        self.assertFalse(True)

    def test_webhook_push_made_on_preview_is_ignored(self):
        self.assertFalse(True)
