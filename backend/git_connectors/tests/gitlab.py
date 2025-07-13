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

GITLAB_ACCESS_TOKEN_DATA = {
    "access_token": "de6780bc506a0446309bd9362820ba8aed28aa506c71eedbe1c5c4f9dd350e54",
    "token_type": "bearer",
    "expires_in": 7200,
    "refresh_token": "8257e65c97202ed1726cf9571600918f3bffb2544b26e00a61df9897668c33a1",
    "created_at": 1607635748,
}

GITLAB_PROJECT_LIST = [
    {
        "id": 4,
        "description": None,
        "name": "Diaspora Client",
        "name_with_namespace": "Diaspora / Diaspora Client",
        "path": "diaspora-client",
        "path_with_namespace": "diaspora/diaspora-client",
        "created_at": "2013-09-30T13:46:02Z",
        "default_branch": "main",
        "tag_list": ["example", "disapora client"],
        "topics": ["example", "disapora client"],
        "ssh_url_to_repo": "git@gitlab.example.com:diaspora/diaspora-client.git",
        "http_url_to_repo": "https://gitlab.example.com/diaspora/diaspora-client.git",
        "web_url": "https://gitlab.example.com/diaspora/diaspora-client",
        "avatar_url": "https://gitlab.example.com/uploads/project/avatar/4/uploads/avatar.png",
        "star_count": 0,
        "last_activity_at": "2013-09-30T13:46:02Z",
        "namespace": {
            "id": 2,
            "name": "Diaspora",
            "path": "diaspora",
            "kind": "group",
            "full_path": "diaspora",
            "parent_id": None,
            "avatar_url": None,
            "web_url": "https://gitlab.example.com/diaspora",
        },
        "visibility": "public",
        "permissions": {
            "project_access": {
                "access_level": 40,  # Maintainer
                "notification_level": 3,
            },
            "group_access": None,
        },
    },
    {
        "id": 71408858,
        "description": None,
        "name": "M346 Ref Card 03",
        "name_with_namespace": "Mykola Zabielin / M346 Ref Card 03",
        "path": "m346-ref-card-03",
        "path_with_namespace": "SomeOneUnkn0wn/m346-ref-card-03",
        "created_at": "2025-07-06T18:53:00.603Z",
        "default_branch": "main",
        "tag_list": [],
        "topics": [],
        "ssh_url_to_repo": "git@gitlab.com:SomeOneUnkn0wn/m346-ref-card-03.git",
        "http_url_to_repo": "https://gitlab.com/SomeOneUnkn0wn/m346-ref-card-03.git",
        "web_url": "https://gitlab.com/SomeOneUnkn0wn/m346-ref-card-03",
        "readme_url": "https://gitlab.com/SomeOneUnkn0wn/m346-ref-card-03/-/blob/main/README.md",
        "forks_count": 0,
        "avatar_url": None,
        "star_count": 0,
        "last_activity_at": "2025-07-06T18:53:00.513Z",
        "namespace": {
            "id": 105246917,
            "name": "Mykola Zabielin",
            "path": "SomeOneUnkn0wn",
            "kind": "user",
            "full_path": "SomeOneUnkn0wn",
            "parent_id": None,
            "avatar_url": "https://secure.gravatar.com/avatar/cb433e7bfdebc0d5fa0ad338774ad1e3d662aa79190edc714af55cae4e7c464b?s=80&d=identicon",
            "web_url": "https://gitlab.com/SomeOneUnkn0wn",
        },
        "visibility": "private",
        "permissions": {
            "project_access": {
                "access_level": 30,  # Developer
                "notification_level": 3,
            },
            "group_access": None,
        },
    },
    {
        "id": 71408856,
        "description": None,
        "name": "Private Ac",
        "name_with_namespace": "Fred Kiss / Private Ac",
        "path": "private-ac",
        "path_with_namespace": "fredkiss3/private-ac",
        "created_at": "2025-07-06T18:52:53.253Z",
        "default_branch": "main",
        "tag_list": [],
        "topics": [],
        "ssh_url_to_repo": "git@gitlab.com:fredkiss3/private-ac.git",
        "http_url_to_repo": "https://gitlab.com/fredkiss3/private-ac.git",
        "web_url": "https://gitlab.com/fredkiss3/private-ac",
        "readme_url": "https://gitlab.com/fredkiss3/private-ac/-/blob/main/README.md",
        "forks_count": 0,
        "avatar_url": None,
        "visibility": "private",
        "star_count": 0,
        "last_activity_at": "2025-07-06T18:52:53.165Z",
        "namespace": {
            "id": 10493765,
            "name": "Fred Kiss",
            "path": "fredkiss3",
            "kind": "user",
            "full_path": "fredkiss3",
            "parent_id": None,
            "avatar_url": "https://secure.gravatar.com/avatar/9772ec11911021f7f3ae40e76789e67dd20b0f27e609d0e67d5479985c237169?s=80&d=identicon",
            "web_url": "https://gitlab.com/fredkiss3",
        },
        "permissions": {
            "project_access": {
                "access_level": 50,  # Owner
                "notification_level": 3,
            },
            "group_access": None,
        },
    },
]


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
