import re
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Project, Service
from ..models import GitHubApp, GitRepository
from ..serializers import GithubWebhookEvent
from unittest.mock import patch, MagicMock
from .github import (
    MANIFEST_DATA,
    INSTALLATION_CREATED_WEBHOOK_DATA,
    get_signed_event_headers,
)


class DeployGitServiceFromGithubAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_deploy_service_apply_git_app_changes(self):
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

        created_service = Service.objects.get(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        )

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": created_service.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        created_service.refresh_from_db()
        self.assertIsNotNone(created_service.git_app)  # type: ignore

    @responses.activate
    def test_deploy_service_apply_git_app_changes_list_repo_using_access_token(self):
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

        # create service
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

        mock_git = MagicMock()
        with patch("zane_api.git_client.Git", return_value=mock_git):
            mock_git.ls_remote.side_effect = self.fake_git.ls_remote
            # deploy service
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

            git_repo = GitRepository.objects.get(
                url="https://github.com/Fredkiss3/private-ac"
            )
            url = gh_app.get_authenticated_repository_url(git_repo.url + ".git")
            mock_git.ls_remote.assert_called_with("--heads", url, "main")

    @responses.activate
    async def test_deploy_service_with_git_app_changes_clone_with_access_token(self):
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

        created_service = Service.objects.get(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        )

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": created_service.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        created_service.refresh_from_db()
        self.assertIsNotNone(created_service.git_app)  # type: ignore


class UpdateGitServiceFromGithubAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_update_service_with_git_app_changes_validate_gitapp(self):
        raise NotImplementedError()
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

        created_service = Service.objects.get(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        )

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": created_service.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        created_service.refresh_from_db()
        self.assertIsNotNone(created_service.git_app)  # type: ignore
