import json
import re
from typing import cast
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp
from ..models import GitlabApp
from ..serializers import GithubWebhookEvent
import hashlib
import hmac
from django.core.cache import cache
from django.conf import settings

"""
workflow: 
User Form:
    1. Submit : name, app_id, app_secret, redirect_URI, gitlab_url
    2. ZaneOps API sends `STATE` (STATE => random ID in cache, storing the app_id, client_secret & redirect_uri)
    3. redirects to : https://gitlab.example.com/oauth/authorize?client_id=APP_ID
                        &redirect_uri=REDIRECT_URI
                        &response_type=code
                        &state=STATE
                        &scope={api+read_user+read_repository}
    4. redirects back to /api/connectors/gitlab/setup?code=1234567890&state=STATE
    5. Get `refresh_token` & save Gitlab app, then fetch all repositories 
    6. redirects to `/settings/git-apps` (frontend)
"""

GITLAB_ACCESS_TOKEN_DATA = {
    "access_token": "de6780bc506a0446309bd9362820ba8aed28aa506c71eedbe1c5c4f9dd350e54",
    "token_type": "bearer",
    "expires_in": 7200,
    "refresh_token": "8257e65c97202ed1726cf9571600918f3bffb2544b26e00a61df9897668c33a1",
    "created_at": 1607635748,
}


class TestSetupGitlabConnectorViewTests(AuthAPITestCase):
    def test_create_gitlab_app_creates_state_in_cache(self):
        self.loginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            "gitlab_url": "https://gitlab.com",
            "name": "foxylab",
        }
        response = self.client.post(reverse("git_connectors:gitlab.create"), data=body)

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        state = response.json()["state"]
        self.assertEqual(body, cache.get(f"{GitlabApp.STATE_CACHE_PREFIX}:{state}"))

        self.assertEqual(0, GitApp.objects.count())
        self.assertEqual(0, GitlabApp.objects.count())

    @responses.activate
    def test_setup_gitlab_app_creates_and_validates_gitlab_app(self):
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

        params = {
            "code": generate_random_chars(10),
            "state": state,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        # delete state in cache to prevent abuse
        self.assertEqual(None, cache.get(f"{GitlabApp.STATE_CACHE_PREFIX}:{state}"))

        self.assertEqual(1, GitApp.objects.count())
        gitapp = cast(GitApp, GitApp.objects.first())
        self.assertIsNotNone(gitapp.gitlab)

        gitlab = cast(GitlabApp, gitapp.gitlab)
        self.assertEqual("foxylab", gitlab.name)
        self.assertEqual("https://gitlab.com", gitlab.gitlab_url)
        self.assertEqual(body["redirect_uri"], gitlab.redirect_uri)
        self.assertGreater(len(gitlab.refresh_token), 0)
        self.assertGreater(len(gitlab.app_id), 0)
        self.assertGreater(len(gitlab.secret), 0)
