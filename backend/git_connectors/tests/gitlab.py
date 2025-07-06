import json
import re
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

"""
workflow: 
User Form:
    1. Submit : app_id, app_secret & redirect_URI
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


class TestSetupGitlabConnectorViewTests(AuthAPITestCase):
    def test_create_gitlab_app_creates_state_in_cache(self):
        self.loginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": "http://app.zaneops.local/api/connectors/gitlab/setup",
        }
        response = self.client.post(reverse("git_connectors:gitlab.create"), data=body)

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        state = response.json()["state"]
        self.assertEqual(body, cache.get(state))

        self.assertEqual(0, GitApp.objects.count())
        self.assertEqual(0, GitlabApp.objects.count())
