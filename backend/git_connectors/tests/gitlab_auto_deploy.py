import re
from typing import cast
from urllib.parse import urlencode
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Deployment
from ..models import GitHubApp, GitlabApp
from ..serializers import GithubWebhookEvent
from .gitlab import GITLAB_ACCESS_TOKEN_DATA, GITLAB_PROJECT_LIST

GITLAB_PROJECT_WEBHOOK_API_DATA = {
    "id": 789542,
    "url": "http://127-0-0-1.sslip.io/api/connectors/gilab/webhook",
    "name": None,
    "description": None,
    "created_at": "2025-07-13T02:32:23.812Z",
    "push_events": True,
    "tag_push_events": False,
    "merge_requests_events": False,
    "repository_update_events": False,
    "enable_ssl_verification": True,
    "alert_status": "executable",
    "disabled_until": None,
    "url_variables": [],
    "push_events_branch_filter": None,
    "branch_filter_strategy": "wildcard",
    "custom_webhook_template": None,
    "custom_headers": [],
    "project_id": 15546,
    "issues_events": False,
    "confidential_issues_events": False,
    "note_events": False,
    "confidential_note_events": None,
    "pipeline_events": False,
    "wiki_page_events": False,
    "deployment_events": False,
    "feature_flag_events": False,
    "job_events": False,
    "releases_events": False,
    "milestone_events": False,
    "emoji_events": False,
    "resource_access_token_events": False,
    "vulnerability_events": False,
}


class BaseGitlabTestAPITestCase(AuthAPITestCase):
    @responses.activate
    def create_gitlab_app(self):
        self.loginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
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

        params = {
            "code": generate_random_chars(10),
            "state": state,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)
        return GitlabApp.objects.get(app_id=body["app_id"])


class TestCreateGitlabWebhookAPIView(BaseGitlabTestAPITestCase):
    @responses.activate
    def test_create_webhooks_in_projects_when_setting_up_gitlab_app(self):
        gitlab_project_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/[0-9+]/hooks",
            re.IGNORECASE,
        )
        mock_response = responses.add(
            responses.POST,
            url=gitlab_project_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_PROJECT_WEBHOOK_API_DATA,
        )
        self.create_gitlab_app()

        # We have 3 projects, but only two have the required maintainer level
        self.assertEqual(2, mock_response.call_count)
