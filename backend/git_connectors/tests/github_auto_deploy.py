import re
from typing import cast
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Deployment
from ..models import GitHubApp
from ..serializers import GithubWebhookEvent
from .fixtures import (
    GITHUB_PUSH_WEBHOOK_EVENT_DATA,
    get_github_signed_event_headers,
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
)


class DeployGithubServiceFromWebhookPushViewTests(AuthAPITestCase):
    @responses.activate
    async def test_deploy_service_from_push_webhook_deploy_service_succesfully(self):
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
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

        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PUSH_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                GITHUB_PUSH_WEBHOOK_EVENT_DATA,
                gh_app.webhook_secret,
            ),
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

        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["message"],
            new_deployment.commit_message,
        )
        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["id"],
            new_deployment.commit_sha,
        )
        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["author"]["name"],
            new_deployment.commit_author_name,
        )

    @responses.activate
    async def test_deploy_service_from_push_webhook_using_slash_in_branch_deploy_service_succesfully(
        self,
    ):
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
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

        p, service = await self.acreate_git_service(
            branch_name="docs/v-1.11",
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )
        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["ref"] = "refs/heads/docs/v-1.11"
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
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

        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["message"],
            new_deployment.commit_message,
        )
        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["id"],
            new_deployment.commit_sha,
        )
        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["author"]["name"],
            new_deployment.commit_author_name,
        )

    @responses.activate
    async def test_push_to_a_different_branch_do_not_deploy_the_service(self):
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
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
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )

        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["ref"] = "refs/heads/testing"
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await service.deployments.acount())

    @responses.activate
    async def test_push_to_a_non_branch_do_not_deploy_the_service(self):
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
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
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )

        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["ref"] = "refs/tags/main"
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await service.deployments.acount())

    @responses.activate
    async def test_github_pushes_ignore_unwatched_paths(self):
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
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
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )
        service.watch_paths = "routes/api/*"
        await service.asave()

        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PUSH_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                GITHUB_PUSH_WEBHOOK_EVENT_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(0, await service.deployments.acount())

    @responses.activate
    async def test_deploy_service_from_github_push_with_empty_head_commit_resolves_commit_from_HEAD(
        self,
    ):
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
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
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

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )

        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["head_commit"] = None
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
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
