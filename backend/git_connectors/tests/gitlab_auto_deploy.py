import re
from typing import cast
from urllib.parse import urlencode
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Deployment, DeploymentChange
from ..models import GitHubApp, GitlabApp
from ..serializers import GitlabWebhookEvent, GithubWebhookEvent

from asgiref.sync import sync_to_async


from .fixtures import (
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
    GITLAB_PUSH_WEBHOOK_EVENT_DATA,
    GITLAB_PROJECT_LIST,
    GITLAB_ACCESS_TOKEN_DATA,
    GITLAB_PROJECT_WEBHOOK_API_DATA,
    get_github_signed_event_headers,
)


class TestGitlabPushWebhookAPIView(AuthAPITestCase):
    def create_gitlab_app(self, with_webhook: bool = True):
        self.loginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
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

        if with_webhook:
            gitlab_project_api_pattern = re.compile(
                r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
                re.IGNORECASE,
            )
            responses.add(
                responses.POST,
                url=gitlab_project_api_pattern,
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
        return (
            GitApp.objects.filter(gitlab__app_id=body["app_id"])
            .select_related("gitlab")
            .get()
        )

    @responses.activate
    def test_create_webhooks_in_projects_when_setting_up_gitlab_app(self):
        gitlab_project_api_pattern = re.compile(
            r"https://gitlab\.com/api/v4/projects/[0-9]+/hooks",
            re.IGNORECASE,
        )
        mock_response = responses.add(
            responses.POST,
            url=gitlab_project_api_pattern,
            status=status.HTTP_200_OK,
            json=GITLAB_PROJECT_WEBHOOK_API_DATA,
        )
        self.create_gitlab_app(False)

        # We have 3 projects, so this endpoint should be called 3 times
        self.assertEqual(3, mock_response.call_count)

    @responses.activate
    async def test_deploy_service_from_gitlab_push_webhook_deploy_service_succesfully(
        self,
    ):
        app: GitApp = await sync_to_async(self.create_gitlab_app)()
        gitlab = cast(GitlabApp, app.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, service = await self.acreate_git_service(
            repository_url="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=app.id,
        )
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_PUSH_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.PUSH,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment = cast(Deployment, await service.alatest_production_deployment)
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)
        self.assertEqual(
            Deployment.DeploymentTriggerMethod.AUTO, new_deployment.trigger_method
        )

        head_commit = GITLAB_PUSH_WEBHOOK_EVENT_DATA["commits"][-1]
        self.assertEqual(
            head_commit["id"],
            new_deployment.commit_sha,
        )
        self.assertEqual(
            head_commit["message"],
            new_deployment.commit_message,
        )
        self.assertEqual(
            head_commit["author"]["name"],
            new_deployment.commit_author_name,
        )

    @responses.activate
    async def test_deploy_service_from_gitlab_push_with_empty_commits_resolves_commit_from_HEAD(
        self,
    ):
        app: GitApp = await sync_to_async(self.create_gitlab_app)()
        gitlab = cast(GitlabApp, app.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, service = await self.acreate_git_service(
            repository_url="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=app.id,
        )

        new_data = dict(**GITLAB_PUSH_WEBHOOK_EVENT_DATA)
        new_data["commits"] = []
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=new_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.PUSH,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment = cast(Deployment, await service.alatest_production_deployment)
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)
        self.assertEqual(
            Deployment.DeploymentTriggerMethod.AUTO, new_deployment.trigger_method
        )

        self.assertEqual(
            self.fake_git.DEFAULT_COMMIT_SHA,
            new_deployment.commit_sha,
        )
        self.assertEqual(
            self.fake_git.DEFAULT_COMMIT_MESSAGE,
            new_deployment.commit_message,
        )
        self.assertEqual(
            self.fake_git.DEFAULT_COMMIT_AUTHOR_NAME,
            new_deployment.commit_author_name,
        )

    @responses.activate
    async def test_deploy_service_from_gitlab_changing_ignore_if_pending_changes_conflicts(
        self,
    ):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        # CREATE & INSTALL GITLAB APP
        await self.aLoginUser()
        body = {
            "app_id": generate_random_chars(10),
            "app_secret": generate_random_chars(40),
            "redirect_uri": f"https://{settings.ZANE_APP_DOMAIN}/api/connectors/gitlab/setup",
            "gitlab_url": "https://gitlab.com",
            "name": "foxylab",
        }
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.create"), data=body
        )

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
        response = await self.async_client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)
        git_gitlab = await (
            GitApp.objects.filter(gitlab__app_id=body["app_id"])
            .select_related("gitlab")
            .aget()
        )

        # Deploy the service first with Gitlab
        p, service = await self.acreate_and_deploy_git_service(
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=git_gitlab.id,
        )

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

        # CREATE & INSTALL GITHUB APP
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_github = await GitApp.objects.acreate(github=gh_app)
        # install app
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Then update the changes to GitHub
        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/Fredkiss3/private-ac",
                "git_app_id": git_github.id,
            },
        }
        response = await self.async_client.put(
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

        ## AND NOW TRIGGER THE WEBHOOK
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_PUSH_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.PUSH,
                "X-Gitlab-Token": git_gitlab.gitlab.webhook_secret,  # type: ignore
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # this should not trigger a new deployment
        self.assertEqual(1, await service.deployments.acount())
        self.assertEqual(1, await service.unapplied_changes.acount())
