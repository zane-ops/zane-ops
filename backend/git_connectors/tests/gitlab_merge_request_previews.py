import json
import re
from typing import cast

import responses
from ..serializers.gitlab import GitlabWebhookEvent
from zane_api.tests.base import AuthAPITestCase
from .fixtures import (
    GITLAB_PROJECT_LIST,
    GITLAB_ACCESS_TOKEN_DATA,
    GITLAB_PROJECT_WEBHOOK_API_DATA,
    GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
)

from urllib.parse import urlencode

from copy import deepcopy
from asgiref.sync import sync_to_async
from rest_framework import status
from zane_api.utils import generate_random_chars, jprint
from ..models import GitHubApp, GitlabApp
from zane_api.models import (
    GitApp,
    Service,
    Deployment,
    DeploymentChange,
    ArchivedEnvironment,
)
from django.urls import reverse
from zane_api.models import Environment, PreviewEnvMetadata
from django.conf import settings
from zane_api.views.serializers import PreviewEnvDeployDecision


class BaseGitlabMergeRequestViewTestCase(AuthAPITestCase):
    def create_gitlab_app(self, with_webhook: bool = True):
        self.loginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            "gitlab_url": "https://gitlab.com",
            "name": "foxylab",
        }
        response = self.client.post(reverse("git_connectors:gitlab.create"), data=body)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        state = response.json()["state"]

        gitlab_api_pattern = re.compile(
            r"https://gitlab\.com/oauth/token/?",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_ACCESS_TOKEN_DATA,
        )

        gitlab_project_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/?",
            re.IGNORECASE,
        )
        responses.add(
            responses.GET,
            url=gitlab_project_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_PROJECT_LIST,
        )
        responses.add(
            responses.GET,
            url=gitlab_project_api_pattern,
            status=status.HTTP_200_OK,
            json=[],
        )

        if with_webhook:
            gitlab_project_api_pattern = re.compile(
                r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
                re.IGNORECASE,
            )
            responses.add(
                responses.POST,
                url=gitlab_project_api_pattern,
                status=status.HTTP_200_OK,
                json=GITLAB_PROJECT_WEBHOOK_API_DATA,
            )

        params = {
            "code": generate_random_chars(10),
            "state": state,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)
        return (
            GitApp.objects.filter(gitlab__app_id=body["app_id"])
            .select_related("gitlab")
            .get()
        )

    async def acreate_gitlab_app(self, with_webhook: bool = True):
        return await sync_to_async(self.create_gitlab_app)(with_webhook)


class CreateGitlabMergeRequestPreviewEnvGitlabViewTests(
    BaseGitlabMergeRequestViewTestCase
):

    @responses.activate
    def test_open_merge_request_should_create_preview_env(self):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitlabApp, gitapp.gitlab)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
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

        mr_data = GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA["object_attributes"]
        event_data = GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA

        self.assertTrue(
            preview_env.name.startswith(f"preview-mr-{mr_data['iid']}-{service.slug}")
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(mr_data["source_branch"], preview_meta.branch_name)
        repo_url = mr_data["source"]["git_http_url"]
        self.assertEqual(repo_url, preview_meta.head_repository_url)
        self.assertEqual(
            mr_data["url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.APPROVED,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            mr_data["iid"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            mr_data["title"],
            preview_meta.pr_title,
        )
        self.assertEqual(
            event_data["user"]["username"],
            preview_meta.pr_author,
        )
        self.assertEqual(
            mr_data["target"]["git_http_url"],
            preview_meta.pr_base_repo_url,
        )
        self.assertEqual(
            mr_data["target_branch"],
            preview_meta.pr_base_branch_name,
        )
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_meta.template
        )
        self.assertEqual(service, preview_meta.service)
        self.assertEqual(gitapp, preview_meta.git_app)
        self.assertEqual("HEAD", preview_meta.commit_sha)

        self.assertEqual(1, preview_env.services.count())
