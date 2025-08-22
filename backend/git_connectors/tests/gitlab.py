import re
from typing import cast
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp
from ..models import GitlabApp, GitRepository

from django.core.cache import cache
from django.conf import settings
from .fixtures import (
    GITLAB_ACCESS_TOKEN_DATA,
    GITLAB_PROJECT_LIST,
    GITLAB_PROJECT_WEBHOOK_API_DATA,
)


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
        self.assertEqual(body, cache.get(state))

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
        gitlab_project_hooks_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_project_hooks_api_pattern,
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

        # delete state in cache to prevent abuse
        self.assertEqual(None, cache.get(state))

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

    @responses.activate
    def test_setup_gitlab_app_validate_state_data(self):
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
            "state": "whatever",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    def test_setup_gitlab_with_different_gitlab_url_store_it_correctly(self):
        self.loginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            "gitlab_url": "https://gitlab.example.com",
            "name": "foxylab",
        }
        response = self.client.post(reverse("git_connectors:gitlab.create"), data=body)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        state = response.json()["state"]

        gitlab_api_pattern = re.compile(
            r"https://gitlab\.example\.com/oauth/token/?",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_ACCESS_TOKEN_DATA,
        )

        gitlab_project_api_pattern = re.compile(
            r"https://gitlab\.example\.com/api/v4/projects/?",
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
        gitlab_project_hooks_api_pattern = re.compile(
            r"https://gitlab\.example\.com/api/v4/projects/[0-9]+/hooks",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_project_hooks_api_pattern,
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

        # delete state in cache to prevent abuse
        self.assertEqual(None, cache.get(state))

        self.assertEqual(1, GitApp.objects.count())
        gitapp = cast(GitApp, GitApp.objects.first())
        self.assertIsNotNone(gitapp.gitlab)

        gitlab = cast(GitlabApp, gitapp.gitlab)
        self.assertEqual("https://gitlab.example.com", gitlab.gitlab_url)

    @responses.activate
    def test_setup_gitlab_app_fetches_repositories_from_project(self):
        self.loginUser()
        gitlab_token_api_pattern = re.compile(
            r"https://gitlab\.com/oauth/token/?",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_token_api_pattern,
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
        gitlab_project_hooks_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_project_hooks_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_PROJECT_WEBHOOK_API_DATA,
        )

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

        params = {
            "code": generate_random_chars(10),
            "state": state,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        self.assertEqual(1, GitApp.objects.count())
        gitapp = cast(GitApp, GitApp.objects.first())
        self.assertIsNotNone(gitapp.gitlab)

        gitlab = cast(GitlabApp, gitapp.gitlab)
        self.assertEqual(3, gitlab.repositories.count())

    @responses.activate
    def test_fetching_gitlab_repositories_is_idempotent(self):
        self.loginUser()
        gitlab_token_api_pattern = re.compile(
            r"https://gitlab\.com/oauth/token/?",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_token_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_ACCESS_TOKEN_DATA,
        )

        gitlab_project_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/?.+",
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
        gitlab_project_hooks_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_project_hooks_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_PROJECT_WEBHOOK_API_DATA,
        )

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

        params = {
            "code": generate_random_chars(10),
            "state": state,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        gitapp = cast(GitApp, GitApp.objects.first())
        gitlab = cast(GitlabApp, gitapp.gitlab)

        gitlab.fetch_all_repositories_from_gitlab()
        gitlab.fetch_all_repositories_from_gitlab()
        self.assertEqual(3, gitlab.repositories.count())

        self.assertEqual(3, GitRepository.objects.count())


class TestUpdateGitlabConnectorViewTests(AuthAPITestCase):
    @responses.activate
    def test_update_gitlab_keeps_state_update_in_cache(self):
        self.loginUser()
        initial_secret = generate_random_chars(40)
        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=initial_secret,
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        _ = GitApp.objects.create(gitlab=gitlab)

        body = {
            "app_secret": generate_random_chars(40),
            "name": "foxylab2",
            "redirect_uri": f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
        }
        response = self.client.put(
            reverse("git_connectors:gitlab.update", kwargs={"id": gitlab.id}),
            data=body,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        state = response.json()["state"]
        self.assertEqual(
            dict(
                app_secret=body["app_secret"],
                app_id=gitlab.app_id,
                redirect_uri=f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            ),
            cache.get(state),
        )
        gitlab.refresh_from_db()
        self.assertEqual("foxylab2", gitlab.name)
        self.assertEqual(initial_secret, gitlab.secret)

    @responses.activate
    def test_update_gitlab_updates_secret_and_refetch_repos(self):
        gitlab_token_api_pattern = re.compile(
            r"https://gitlab\.com/oauth/token/?",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_token_api_pattern,
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
        gitlab_project_hooks_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=gitlab_project_hooks_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_PROJECT_WEBHOOK_API_DATA,
        )

        self.loginUser()
        initial_secret = generate_random_chars(40)
        initial_refresh_token = generate_random_chars(64)
        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=initial_secret,
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=initial_refresh_token,
        )
        _ = GitApp.objects.create(gitlab=gitlab)

        body = {
            "app_secret": generate_random_chars(40),
            "name": "foxylab2",
            "redirect_uri": f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
        }
        response = self.client.put(
            reverse("git_connectors:gitlab.update", kwargs={"id": gitlab.id}),
            data=body,
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        state = response.json()["state"]

        params = {
            "code": generate_random_chars(10),
            "state": state,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        # state deleted from cache
        self.assertIsNone(cache.get(state))
        gitlab.refresh_from_db()
        self.assertEqual("foxylab2", gitlab.name)
        self.assertEqual(body["app_secret"], gitlab.secret)
        self.assertEqual(body["redirect_uri"], gitlab.redirect_uri)
        self.assertNotEqual(initial_refresh_token, gitlab.refresh_token)
        self.assertEqual(3, gitlab.repositories.count())
