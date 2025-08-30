import re
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp
from ..models import GitHubApp, GitRepository
from ..serializers import GithubWebhookEvent
from .fixtures import (
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_PING_WEBHOOK_DATA,
    get_github_signed_event_headers,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
    GITHUB_INSTALLATION_REPOS_ADDED_WEBHOOK_DATA,
    GITHUB_INSTALLATION_REPOS_REMOVED_WEBHOOK_DATA,
)


class TestSetupGithubConnectorViewTests(AuthAPITestCase):

    @responses.activate
    def test_setup_connector_creates_github_app_sucessful(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https://api\.github\.com/app-manifests/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json=GITHUB_APP_MANIFEST_DATA,
        )

        params = {
            "code": generate_random_chars(10),
            "state": "create",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        self.assertEqual(1, GitApp.objects.count())
        git_app: GitApp = GitApp.objects.first()  # type: ignore
        self.assertIsNotNone(git_app.github)

        github_app: GitHubApp = git_app.github  # type: ignore
        self.assertEqual(GITHUB_APP_MANIFEST_DATA["id"], github_app.app_id)
        self.assertEqual(GITHUB_APP_MANIFEST_DATA["name"], github_app.name)
        self.assertEqual(GITHUB_APP_MANIFEST_DATA["client_id"], github_app.client_id)
        self.assertEqual(
            GITHUB_APP_MANIFEST_DATA["client_secret"], github_app.client_secret
        )
        self.assertEqual(
            GITHUB_APP_MANIFEST_DATA["webhook_secret"], github_app.webhook_secret
        )
        self.assertEqual(GITHUB_APP_MANIFEST_DATA["pem"], github_app.private_key)
        self.assertEqual(GITHUB_APP_MANIFEST_DATA["html_url"], github_app.app_url)

        self.assertFalse(git_app.github.is_installed)  # type: ignore

    @responses.activate
    def test_setup_connector_install_github_app(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https://api\.github\.com/app-manifests/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json=GITHUB_APP_MANIFEST_DATA,
        )

        params = {
            "code": generate_random_chars(10),
            "state": "create",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        git_app: GitApp = GitApp.objects.first()  # type: ignore
        github_app: GitHubApp = git_app.github  # type: ignore

        params = {
            "code": generate_random_chars(10),
            "state": f"install:{github_app.id}",
            "installation_id": 1,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        github_app.refresh_from_db()
        self.assertTrue(git_app.github.is_installed)  # type: ignore

    def test_setup_connector_non_existent_gh_app(self):
        self.loginUser()

        params = {
            "code": generate_random_chars(10),
            "state": f"install:{GitHubApp.ID_PREFIX}abcd12",
            "installation_id": 1,
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_setup_connector_install_with_no_installation_id(self):
        self.loginUser()

        params = {
            "code": generate_random_chars(10),
            "state": f"install:{GitHubApp.ID_PREFIX}abcd12",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    def test_setup_connector_creates_github_app_fails(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https://api\.github\.com/app-manifests/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_404_NOT_FOUND,
            json={"data": "Page not found"},
        )

        params = {
            "code": generate_random_chars(10),
            "state": "create",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        self.assertEqual(0, GitApp.objects.count())
        self.assertEqual(0, GitHubApp.objects.count())


class TestGithubWebhookAPIViewTests(AuthAPITestCase):
    def test_github_webhook_respond_to_ping(self):
        self.loginUser()
        gh_app = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PING_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PING,
                GITHUB_PING_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_github_webhook_validate_bad_signature(self):
        self.loginUser()
        gh_app = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PING_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                "ping",
                GITHUB_PING_WEBHOOK_DATA,
                "fake",
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_github_webhook_non_existent(self):
        self.loginUser()

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PING_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                "ping",
                GITHUB_PING_WEBHOOK_DATA,
                "fake",
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_github_webhook_add_repositories_on_app_installation_webhook(self):
        self.loginUser()
        gh_app = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(6, gh_app.repositories.count())

    def test_github_webhook_add_repositories_on_app_installation_webhook_is_idempotent(
        self,
    ):
        self.loginUser()
        gh_app = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(6, gh_app.repositories.count())

    def test_github_webhook_installation_repositories_added(self):
        self.loginUser()
        gh_app = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_REPOS_ADDED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION_REPOS,
                GITHUB_INSTALLATION_REPOS_ADDED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(8, gh_app.repositories.count())

    def test_github_webhook_installation_repositories_removed(self):
        self.loginUser()
        gh_app = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_REPOS_REMOVED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION_REPOS,
                GITHUB_INSTALLATION_REPOS_REMOVED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, gh_app.repositories.count())
        self.assertEqual(3, GitRepository.objects.count())
