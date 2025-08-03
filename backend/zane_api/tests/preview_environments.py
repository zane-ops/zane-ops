from typing import cast
from urllib.parse import urlencode
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    Deployment,
    Service,
    # ArchivedDockerService,
    Environment,
    DeploymentChange,
    # Volume,
    # URL,
    GitApp,
    PreviewTemplate,
)

from django.conf import settings

from ..utils import jprint, generate_random_chars, find_item_in_sequence
import responses
import re

from git_connectors.models import GitHubApp, GitlabApp
from git_connectors.views import GithubWebhookEvent
from asgiref.sync import sync_to_async
from django.utils.text import slugify
from git_connectors.tests.fixtures import (
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
    GITHUB_PUSH_WEBHOOK_EVENT_DATA,
    GITLAB_PUSH_WEBHOOK_EVENT_DATA,
    GITLAB_ACCESS_TOKEN_DATA,
    GITLAB_PROJECT_LIST,
    GITLAB_PROJECT_WEBHOOK_API_DATA,
    get_github_signed_event_headers,
)
from git_connectors.constants import GITLAB_NULL_COMMIT
from git_connectors.views.gitlab import GitlabWebhookEvent


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


class PreviewEnvironmentsViewTests(AuthAPITestCase):
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

    async def acreate_gitlab_app(self, with_webhook: bool = True):
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
        response = await self.async_client.get(
            reverse("git_connectors:gitlab.setup"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)
        return await (
            GitApp.objects.filter(gitlab__app_id=body["app_id"])
            .select_related("gitlab")
            .aget()
        )

    async def acreate_and_install_github_app(self):
        return await sync_to_async(self.create_and_install_github_app)()

    def test_create_default_preview_template_when_creating_a_project(self):
        self.loginUser()
        p, _ = self.create_redis_docker_service()
        default_template = cast(
            PreviewTemplate, p.preview_templates.filter(is_default=True).first()
        )
        self.assertIsNotNone(default_template)
        self.assertEqual(p.production_env, default_template.base_environment)
        self.assertEqual(
            PreviewTemplate.PreviewCloneStrategy.ALL,
            default_template.clone_strategy,
        )
        self.assertEqual(0, default_template.services_to_clone.count())

    def test_prevent_creating_environment_with_preview_prefix(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "preview-staging"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        staging_env = project.environments.filter(name="preview-staging").first()
        self.assertIsNone(staging_env)

    def test_prevent_cloning_environment_with_preview_prefix(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": project.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "preview-staging"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        staging_env = project.environments.filter(name="preview-staging").first()
        self.assertIsNone(staging_env)

    @responses.activate
    def test_trigger_preview_environment_via_deploy_token_create_preview_env_github(
        self,
    ):
        gitapp = self.create_and_install_github_app()

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-1"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertTrue(
            preview_env.name.startswith(f"preview-{slugify('feat/test-1')}")
        )
        self.assertEqual("feat/test-1", preview_env.preview_branch)
        repo_url = cast(str, service.repository_url).removesuffix(".git")
        self.assertEqual(
            f"{repo_url}/tree/feat/test-1",
            preview_env.preview_external_url,
        )
        self.assertEqual(service, preview_env.preview_service)
        self.assertEqual("HEAD", preview_env.preview_commit_sha)
        self.assertEqual(
            Environment.PreviewSourceTrigger.API, preview_env.preview_source_trigger
        )
        self.assertTrue(preview_env.preview_deploy_approved)
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_env.preview_template
        )

    @responses.activate
    def test_trigger_preview_environment_via_deploy_token_create_preview_env_gitlab(
        self,
    ):
        gitapp = self.create_gitlab_app()

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-1"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertTrue(
            preview_env.name.startswith(f"preview-{slugify('feat/test-1')}")
        )
        self.assertEqual("feat/test-1", preview_env.preview_branch)
        repo_url = cast(str, service.repository_url).removesuffix(".git")
        self.assertEqual(
            f"{repo_url}/-/tree/feat/test-1",
            preview_env.preview_external_url,
        )
        self.assertEqual(service, preview_env.preview_service)
        self.assertEqual("HEAD", preview_env.preview_commit_sha)
        self.assertEqual(
            Environment.PreviewSourceTrigger.API, preview_env.preview_source_trigger
        )
        self.assertTrue(preview_env.preview_deploy_approved)
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_env.preview_template
        )

    @responses.activate
    def test_trigger_preview_environment_via_deploy_token_clone_services(self):
        gitapp = self.create_and_install_github_app()

        _, redis_service = self.create_and_deploy_redis_docker_service()
        p, git_service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": git_service.deploy_token},
            ),
            data={"branch_name": "feat/test-1"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertTrue(
            preview_env.name.startswith(f"preview-{slugify('feat/test-1')}")
        )
        self.assertEqual(2, preview_env.services.count())

        # The state changes are applied and deployments are created
        self.assertEqual(
            2,
            Deployment.objects.filter(
                service__environment__name=preview_env.name
            ).count(),
        )

        self.assertEqual(
            0,
            DeploymentChange.objects.filter(
                service__environment__name=preview_env.name, applied=False
            ).count(),
        )

        cloned_git_service = preview_env.services.get(slug=git_service.slug)
        cloned_redis_service = preview_env.services.get(slug=redis_service.slug)
        self.assertEqual(
            redis_service.network_alias, cloned_redis_service.network_alias
        )
        self.assertNotEqual(
            redis_service.global_network_alias,
            cloned_redis_service.global_network_alias,
        )
        self.assertNotEqual(
            redis_service.deploy_token, cloned_redis_service.deploy_token
        )
        self.assertEqual("feat/test-1", cloned_git_service.branch_name)

    @responses.activate
    async def test_trigger_preview_environment_via_deploy_token_deploy_services(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "test-1"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        preview_env = cast(
            Environment, await p.environments.filter(is_preview=True).afirst()
        )
        self.assertIsNotNone(preview_env)

        services_in_preview = Service.objects.filter(environment=preview_env)
        self.assertEqual(2, await services_in_preview.acount())

        self.assertEqual(
            2,
            await Deployment.objects.filter(
                service__environment__name=preview_env.name
            ).acount(),
        )

        self.assertEqual(
            0,
            await DeploymentChange.objects.filter(
                service__environment__name=preview_env.name, applied=False
            ).acount(),
        )
        git_service = await services_in_preview.filter(
            type=Service.ServiceType.GIT_REPOSITORY
        ).afirst()
        docker_service = await services_in_preview.filter(
            type=Service.ServiceType.DOCKER_REGISTRY
        ).afirst()

        swarm_service = self.fake_docker_client.get_deployment_service(
            await git_service.deployments.afirst()  # type: ignore
        )
        self.assertIsNotNone(swarm_service)
        swarm_service = self.fake_docker_client.get_deployment_service(
            await docker_service.deployments.afirst()  # type: ignore
        )
        self.assertIsNotNone(swarm_service)

        service_images = self.fake_docker_client.images_list(
            filters={"label": [f"parent={git_service.id}"]}  # type: ignore
        )
        self.assertEqual(1, len(service_images))

    @responses.activate
    async def test_preview_environment_is_closed_when_branch_is_deleted_for_github(
        self,
    ):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-preview"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        preview_env = cast(
            Environment, await p.environments.filter(is_preview=True).afirst()
        )
        self.assertIsNotNone(preview_env)

        push_data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        # delete branch `test-preview`
        push_data["ref"] = "refs/heads/feat/test-preview"
        push_data["deleted"] = True
        github = cast(GitHubApp, gitapp.github)
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=push_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                push_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await p.environments.filter(is_preview=True).acount())
        self.assertEqual(2, await p.services.acount())
        network = self.fake_docker_client.get_env_network(preview_env)
        self.assertIsNone(network)

    @responses.activate
    async def test_preview_environment_is_closed_when_branch_is_deleted_for_gitlab(
        self,
    ):
        gitapp = await self.acreate_gitlab_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://gitlab.com/fredkiss3/private-ac.git",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-preview"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        preview_env = cast(
            Environment, await p.environments.filter(is_preview=True).afirst()
        )
        self.assertIsNotNone(preview_env)

        push_data = dict(**GITLAB_PUSH_WEBHOOK_EVENT_DATA)
        # delete branch `test-preview`
        push_data["ref"] = "refs/heads/feat/test-preview"
        push_data["after"] = GITLAB_NULL_COMMIT
        push_data["checkout_sha"] = None

        gitlab = cast(GitlabApp, gitapp.gitlab)
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=push_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.PUSH,
                "X-Gitlab-Token": gitlab.webhook_secret,  # type: ignore
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await p.environments.filter(is_preview=True).acount())
        self.assertEqual(2, await p.services.acount())
        network = self.fake_docker_client.get_env_network(preview_env)
        self.assertIsNone(network)

    @responses.activate
    async def test_preview_environment_is_locked_when_push_is_made_to_branch_with_non_head_commit(
        self,
    ):
        self.assertTrue(False)

    def test_create_preview_environment_merge_shared_environment_variables_from_template(
        self,
    ):
        self.assertTrue(False)

    def test_create_preview_environment_with_other_template_only_clone_specified_services(
        self,
    ):
        self.assertTrue(False)

    def test_prevent_renaming_preview_envs(self):
        self.assertTrue(False)

    @responses.activate
    async def test_create_preview_with_invalid_template_errors(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "test-1", "template": "invalid"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    async def test_create_preview_with_invalid_branch_errors(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "branch_name": self.fake_git.NON_EXISTENT_BRANCH,
            },
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
