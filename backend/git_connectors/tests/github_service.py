import re
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Project, Service, DeploymentChange
from ..models import GitHubApp, GitRepository
from ..serializers import GithubWebhookEvent
from unittest.mock import patch, MagicMock
from .github import (
    MANIFEST_DATA,
    INSTALLATION_CREATED_WEBHOOK_DATA,
    get_signed_event_headers,
)

from zane_api.git_client import GitClient
from django.conf import settings


class TestCreateServiceFromGithubAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_create_service_from_github_app_sucessfull(self):
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
        data = response.json()
        self.assertIsNotNone(data)

        created_service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()
        self.assertIsNotNone(created_service)

        source_change = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.GIT_SOURCE
        ).first()
        self.assertIsNotNone(source_change)

        gh_app: GitHubApp = git_app.github  # type: ignore
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/Fredkiss3/private-ac.git",
                "git_app": {
                    "id": git_app.id,
                    "github": {
                        "id": gh_app.id,
                        "name": gh_app.name,
                        "installation_id": gh_app.installation_id,
                        "app_url": gh_app.app_url,
                        "app_id": gh_app.app_id,
                    },
                    "gitlab": None,
                },
            },
            source_change.new_value,  # type: ignore
        )

    def test_create_service_from_github_app_invalid_id(self):
        self.loginUser()

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
            "git_app_id": generate_random_chars(10),
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_service_from_github_app_non_installed(self):
        self.loginUser()

        gh_app = GitHubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_service_from_github_app_invalid_repository(self):
        self.loginUser()
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
            "repository_url": "https://github.com/zane-ops/docs",
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


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

        mock_git = MagicMock(wraps=self.fake_git)
        with patch("zane_api.git_client.Git", return_value=mock_git):
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
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
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

        gh_app = await GitHubApp.objects.acreate(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)

        # install app
        response = await self.async_client.post(
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
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = await Project.objects.aget(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/Fredkiss3/private-ac",
            "branch_name": "main",
            "git_app_id": git_app.id,
        }

        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service = await Service.objects.aget(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        )

        git_client = GitClient()
        mock_git_client = MagicMock(wraps=git_client)
        with patch(
            "temporal.activities.git_activities.GitClient", return_value=mock_git_client
        ):
            response = await self.async_client.put(
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
            called_with_authed_repo_url = all(
                call.kwargs.get("url")
                == gh_app.get_authenticated_repository_url(
                    "https://github.com/Fredkiss3/private-ac.git"
                )
                for call in mock_git_client.aclone_repository.call_args_list
            )
            self.assertTrue(called_with_authed_repo_url)


class UpdateGitServiceFromGithubAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_update_service_with_git_app_changes_is_successfull(self):
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
        # create & install app
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

        # create service & request changes
        p, service = self.create_git_service()

        repo_url = (
            "https://github.com/"
            + INSTALLATION_CREATED_WEBHOOK_DATA["repositories"][0]["full_name"]
        )
        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": repo_url,
                "git_app_id": git_app.id,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        source_change = DeploymentChange.objects.get(
            service=service, field=DeploymentChange.ChangeField.GIT_SOURCE
        )
        self.assertIsNotNone(source_change)

        gh_app: GitHubApp = git_app.github  # type: ignore
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": repo_url + ".git",
                "git_app": {
                    "id": git_app.id,
                    "github": {
                        "id": gh_app.id,
                        "name": gh_app.name,
                        "installation_id": gh_app.installation_id,
                        "app_url": gh_app.app_url,
                        "app_id": gh_app.app_id,
                    },
                    "gitlab": None,
                },
            },
            source_change.new_value,
        )

    def test_update_service_from_github_app_invalid_id(self):
        self.loginUser()

        # create service & request changes
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/Fredkiss3/private-ac",
                "branch_name": "main",
                "git_app_id": generate_random_chars(10),
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_service_from_github_app_non_installed(self):
        self.loginUser()

        gh_app = GitHubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
        )
        git_app = GitApp.objects.create(github=gh_app)

        # create service & request changes
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/Fredkiss3/private-ac",
                "branch_name": "main",
                "git_app_id": git_app.id,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_service_from_github_app_invalid_repository(self):
        self.loginUser()
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

        # create service & request changes
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/zane-ops/docs",
                "branch_name": "main",
                "git_app_id": git_app.id,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    def test_update_service_from_github_app_remove_gitapp(self):
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

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/zane-ops/docs",
                "git_app_id": None,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "docs",
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        source_change = DeploymentChange.objects.filter(
            service__slug="docs", field=DeploymentChange.ChangeField.GIT_SOURCE
        ).first()
        self.assertIsNotNone(source_change)

        gh_app: GitHubApp = git_app.github  # type: ignore
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/zane-ops/docs.git",
                "git_app": None,
            },
            source_change.new_value,  # type: ignore
        )
