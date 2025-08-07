from typing import cast
from urllib.parse import urlencode
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Deployment,
    GitApp,
    PreviewEnvTemplate,
)

from django.conf import settings

from ..utils import jprint, generate_random_chars, find_item_in_sequence
import responses
import re

from git_connectors.models import GitHubApp
from git_connectors.views import GithubWebhookEvent
from git_connectors.tests.fixtures import (
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
    GITLAB_ACCESS_TOKEN_DATA,
    GITLAB_PROJECT_LIST,
    GITLAB_PROJECT_WEBHOOK_API_DATA,
    get_github_signed_event_headers,
)


class MoreEnvironmentViewTests(AuthAPITestCase):
    async def test_deployed_services_are_added_with_global_alias_using_env_id_as_suffix(
        self,
    ):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        deployment = cast(Deployment, await service.deployments.afirst())
        fake_service = self.fake_docker_client.get_deployment_service(deployment)
        global_network_config = find_item_in_sequence(lambda net: net["Target"] == "zane", fake_service.networks)  # type: ignore

        global_aliases = [
            alias
            for alias in global_network_config["Aliases"]  # type: ignore
            if "blue" not in alias and "green" not in alias
        ]
        self.assertEqual(2, len(global_aliases))


class PreviewEnvTestsBase(AuthAPITestCase):

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


class PreviewTemplateViewTests(AuthAPITestCase):
    def create_and_install_github_app(self):
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

        github = GitHubApp.objects.create(
            webhook_secret=GITHUB_APP_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_APP_MANIFEST_DATA["id"],
            name=GITHUB_APP_MANIFEST_DATA["name"],
            client_id=GITHUB_APP_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_APP_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_APP_MANIFEST_DATA["pem"],
            app_url=GITHUB_APP_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        gitapp = GitApp.objects.create(github=github)

        # install app
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return gitapp

    def test_create_preview_template(self):
        p, service = self.create_redis_docker_service()

        response = self.client.post(
            reverse("zane_api:projects.preview_templates", kwargs={"slug": p.slug}),
            data={
                "slug": "new-preview",
                "variables": [
                    {
                        "key": "HELLO",
                        "value": "WORLD",
                    }
                ],
                "clone_strategy": PreviewEnvTemplate.PreviewCloneStrategy.ONLY,
                "services_to_clone_ids": [service.id],
                "base_environment_id": p.production_env.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_preview = cast(
            PreviewEnvTemplate,
            PreviewEnvTemplate.objects.filter(slug="new-preview").first(),
        )
        self.assertIsNotNone(new_preview)

    def test_create_preview_template_already_exists(self):
        p, _ = self.create_redis_docker_service()

        response = self.client.post(
            reverse("zane_api:projects.preview_templates", kwargs={"slug": p.slug}),
            data={
                "slug": "default-preview",
                "base_environment_id": p.production_env.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_create_preview_template_with_clone_strategy_ALL_should_ignore_services_to_clone(
        self,
    ):
        p, service = self.create_redis_docker_service()

        response = self.client.post(
            reverse("zane_api:projects.preview_templates", kwargs={"slug": p.slug}),
            data={
                "slug": "new-preview",
                "variables": [
                    {
                        "key": "HELLO",
                        "value": "WORLD",
                    }
                ],
                "clone_strategy": PreviewEnvTemplate.PreviewCloneStrategy.ALL,
                "services_to_clone_ids": [service.id],
                "base_environment_id": p.production_env.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_preview = PreviewEnvTemplate.objects.get(slug="new-preview")
        self.assertEqual(0, new_preview.services_to_clone.count())

    def test_create_preview_template_with_default_should_remove_default(self):
        p, _ = self.create_redis_docker_service()

        default_template = p.default_preview_template

        response = self.client.post(
            reverse("zane_api:projects.preview_templates", kwargs={"slug": p.slug}),
            data={
                "slug": "new-preview",
                "is_default": True,
                "base_environment_id": p.production_env.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_preview = PreviewEnvTemplate.objects.get(slug="new-preview")
        self.assertTrue(new_preview.is_default)
        self.assertNotEqual(default_template, p.default_preview_template)
        self.assertEqual(new_preview, p.default_preview_template)

    def test_cannot_delete_default_preview_env(self):
        p, _ = self.create_redis_docker_service()

        default_template = p.default_preview_template
        response = self.client.delete(
            reverse(
                "zane_api:projects.preview_templates.details",
                kwargs={"slug": p.slug, "id": default_template.id},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    @responses.activate
    def test_cannot_delete_preview_env_if_used(self):
        gitapp = self.create_and_install_github_app()
        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # Create preview template
        response = self.client.post(
            reverse("zane_api:projects.preview_templates", kwargs={"slug": p.slug}),
            data={
                "slug": "new-preview",
                "base_environment_id": p.production_env.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # trigger preview deploy
        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-1", "template": "new-preview"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # now try to delete the preview
        template = p.preview_templates.get(slug="new-preview")
        response = self.client.delete(
            reverse(
                "zane_api:projects.preview_templates.details",
                kwargs={"slug": p.slug, "id": template.id},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
