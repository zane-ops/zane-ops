import re
from typing import cast
from urllib.parse import urlencode
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Project, Service, DeploymentChange
from ..models import GitRepository, GitlabApp
from unittest.mock import patch, MagicMock


from zane_api.git_client import GitClient
from django.conf import settings
from .gitlab import GITLAB_ACCESS_TOKEN_DATA, GITLAB_PROJECT_LIST


class TestCreateServiceFromGilabAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_create_service_from_gitlab_app_sucessfull(self):
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

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        gitapp = cast(GitApp, GitApp.objects.first())
        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://gitlab.com/fredkiss3/private-ac",
            "branch_name": "main",
            "git_app_id": gitapp.id,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
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

        gitlab = cast(GitlabApp, gitapp.gitlab)
        # jprint(source_change.new_value)  # type: ignore
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://gitlab.com/fredkiss3/private-ac.git",
                "git_app": {
                    "id": gitapp.id,
                    "gitlab": {
                        "id": gitlab.id,
                        "name": gitlab.name,
                        "app_id": gitlab.app_id,
                        "gitlab_url": gitlab.gitlab_url,
                    },
                    "github": None,
                },
            },
            source_change.new_value,  # type: ignore
        )

    def test_create_service_from_gitlab_app_invalid_repository(self):
        self.loginUser()
        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = GitApp.objects.create(gitlab=gitlab)

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://gitlab.com/fredkiss3/private-ac",
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


class DeployGitServiceFromGitlabAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_deploy_service_apply_gitlab_app_changes(self):
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

        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = GitApp.objects.create(gitlab=gitlab)

        gitlab.repositories.add(
            *GitRepository.objects.bulk_create(
                [
                    GitRepository(
                        url=repo["http_url_to_repo"],
                        path=repo["path_with_namespace"],
                        private=repo["visibility"] == "private",
                    )
                    for repo in GITLAB_PROJECT_LIST
                ]
            )
        )

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://gitlab.com/fredkiss3/private-ac",
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
    def test_deploy_service_apply_gitlab_app_changes_list_repo_using_access_token(self):
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

        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = GitApp.objects.create(gitlab=gitlab)

        gitlab.repositories.add(
            *GitRepository.objects.bulk_create(
                [
                    GitRepository(
                        url=repo["http_url_to_repo"],
                        path=repo["path_with_namespace"],
                        private=repo["visibility"] == "private",
                    )
                    for repo in GITLAB_PROJECT_LIST
                ]
            )
        )

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        # create service
        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://gitlab.com/fredkiss3/private-ac",
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
                url="https://gitlab.com/fredkiss3/private-ac.git"
            )
            url = gitlab.get_authenticated_repository_url(git_repo.url)
            mock_git.ls_remote.assert_called_with("--heads", url, "main")

    @responses.activate
    async def test_deploy_service_with_gitlab_app_changes_clone_with_access_token(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
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

        gitlab = await GitlabApp.objects.acreate(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = await GitApp.objects.acreate(gitlab=gitlab)

        await gitlab.repositories.aadd(
            *(
                await GitRepository.objects.abulk_create(
                    [
                        GitRepository(
                            url=repo["http_url_to_repo"],
                            path=repo["path_with_namespace"],
                            private=repo["visibility"] == "private",
                        )
                        for repo in GITLAB_PROJECT_LIST
                    ]
                )
            )
        )

        # create project
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = await Project.objects.aget(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://gitlab.com/fredkiss3/private-ac",
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
                == gitlab.get_authenticated_repository_url(
                    "https://gitlab.com/fredkiss3/private-ac.git"
                )
                for call in mock_git_client.aclone_repository.call_args_list
            )
            self.assertTrue(called_with_authed_repo_url)


class UpdateGitServiceFromGitlabAPIViewTests(AuthAPITestCase):
    @responses.activate
    def test_update_service_with_gitlab_app_changes_is_successfull(self):
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

        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = GitApp.objects.create(gitlab=gitlab)

        gitlab.repositories.add(
            *GitRepository.objects.bulk_create(
                [
                    GitRepository(
                        url=repo["http_url_to_repo"],
                        path=repo["path_with_namespace"],
                        private=repo["visibility"] == "private",
                    )
                    for repo in GITLAB_PROJECT_LIST
                ]
            )
        )

        # create service & request changes
        p, service = self.create_git_service()

        repo_url = "https://gitlab.com/fredkiss3/private-ac"
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

        gitlab = cast(GitlabApp, git_app.gitlab)
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": repo_url + ".git",
                "git_app": {
                    "id": git_app.id,
                    "gitlab": {
                        "id": gitlab.id,
                        "name": gitlab.name,
                        "gitlab_url": gitlab.gitlab_url,
                        "app_id": gitlab.app_id,
                    },
                    "github": None,
                },
            },
            source_change.new_value,
        )

    def test_update_service_from_gitlab_app_invalid_id(self):
        self.loginUser()

        # create service & request changes
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "commit_sha": "HEAD",
                "repository_url": "https://gitlab.com/fredkiss3/private-ac",
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

    def test_update_service_from_gitlab_app_invalid_repository(self):
        self.loginUser()
        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = GitApp.objects.create(gitlab=gitlab)
        gitlab.repositories.add(
            *GitRepository.objects.bulk_create(
                [
                    GitRepository(
                        url=repo["http_url_to_repo"],
                        path=repo["path_with_namespace"],
                        private=repo["visibility"] == "private",
                    )
                    for repo in GITLAB_PROJECT_LIST
                ]
            )
        )

        # create service & request changes
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "commit_sha": "HEAD",
                "repository_url": "https://gitlab.com/fredkiss3/hello-world",
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
    def test_update_service_from_gitlab_app_remove_gitapp(self):
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
        gitlab = GitlabApp.objects.create(
            name="foxylab",
            secret=generate_random_chars(64),
            app_id=generate_random_chars(10),
            redirect_uri=f"http://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            gitlab_url="https://gitlab.com",
            refresh_token=generate_random_chars(64),
        )
        git_app = GitApp.objects.create(gitlab=gitlab)
        gitlab.repositories.add(
            *GitRepository.objects.bulk_create(
                [
                    GitRepository(
                        url=repo["http_url_to_repo"],
                        path=repo["path_with_namespace"],
                        private=repo["visibility"] == "private",
                    )
                    for repo in GITLAB_PROJECT_LIST
                ]
            )
        )

        # create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://gitlab.com/fredkiss3/private-ac",
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
                "repository_url": "https://gitlab.com/zane-ops/docs",
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

        self.assertIsNone(source_change.new_value.get(git_app))  # type: ignore
