import re
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from ..models import GitHubApp
from .github import (
    MANIFEST_DATA,
    INSTALLATION_CREATED_WEBHOOK_DATA,
    get_signed_event_headers,
)
from ..serializers import GithubWebhookEvent
from zane_api.models import GitApp, Project


class TestDeleteGitApp(AuthAPITestCase):
    @responses.activate
    def test_delete_git_app_deletes_github_app(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https:\/\/api\.github\.com\/app-manifests\/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json=MANIFEST_DATA,
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

        response = self.client.delete(
            reverse("git_connectors:git_apps.details", kwargs={"id": git_app.id})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(0, GitApp.objects.count())
        self.assertEqual(0, GitHubApp.objects.count())

    @responses.activate
    def test_cannot_delete_github_app_if_referenced_in_non_deployed_service(self):
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

        gh_app = GitHubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = GitApp.objects.create(github=gh_app)

        # install app
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/Fredkiss3/private-ac",
            "branch_name": "main",
            "git_app_id": git_app.id,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.delete(
            reverse("git_connectors:git_apps.details", kwargs={"id": git_app.id})
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, GitApp.objects.count())
        self.assertEqual(1, GitHubApp.objects.count())

    @responses.activate
    def test_cannot_delete_github_app_if_referenced_in_deployed_service(self):
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

        gh_app = GitHubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = GitApp.objects.create(github=gh_app)

        # install app
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/Fredkiss3/private-ac",
            "branch_name": "main",
            "git_app_id": git_app.id,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "docs",
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.delete(
            reverse("git_connectors:git_apps.details", kwargs={"id": git_app.id})
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, GitApp.objects.count())
        self.assertEqual(1, GitHubApp.objects.count())
