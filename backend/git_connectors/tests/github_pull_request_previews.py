import re
from typing import cast

import responses
from ..serializers.github import GithubWebhookEvent
from zane_api.tests.base import AuthAPITestCase
from .fixtures import (
    GITHUB_APP_MANIFEST_DATA,
    GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
    GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
    GITHUB_PUSH_WEBHOOK_EVENT_DATA,
    GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
    get_github_signed_event_headers,
)

from copy import deepcopy
from asgiref.sync import sync_to_async
from rest_framework import status
from zane_api.utils import generate_random_chars, jprint
from ..models import GitHubApp
from zane_api.models import (
    GitApp,
    Service,
    Deployment,
    DeploymentChange,
    ArchivedEnvironment,
)
from django.urls import reverse
from zane_api.models import Environment, PreviewEnvMetadata
from django.conf import settings
from zane_api.views.serializers import PreviewEnvDeployDecision


class CreatePRPreviewEnvViewTests(AuthAPITestCase):
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

    async def acreate_and_install_github_app(self):
        return await sync_to_async(self.create_and_install_github_app)()

    @responses.activate
    def test_open_pull_request_should_create_preview_env(self):
        gitapp = self.create_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)
        preview_meta = cast(PreviewEnvMetadata, preview_env.preview_metadata)
        self.assertIsNotNone(preview_meta)

        pr_data = GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA["pull_request"]

        self.assertTrue(
            preview_env.name.startswith(
                f"preview-pr-{pr_data['number']}-{service.slug}"
            )
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(pr_data["head"]["ref"], preview_meta.branch_name)
        repo_url = "https://github.com/" + pr_data["head"]["repo"]["full_name"] + ".git"
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(
            pr_data["html_url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.APPROVED,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            pr_data["number"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            pr_data["title"],
            preview_meta.pr_title,
        )
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_meta.template
        )
        self.assertEqual(service, preview_meta.service)
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(gitapp, preview_meta.git_app)
        self.assertEqual("HEAD", preview_meta.commit_sha)

        self.assertEqual(2, preview_env.services.count())

    @responses.activate
    async def test_open_pull_request_should_deploy_services_in_new_preview_env(self):
        gitapp = await self.acreate_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

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
    def test_open_pull_request_twice_is_idempotent(self):
        gitapp = self.create_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)

        self.create_and_deploy_redis_docker_service()
        p, _ = self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive pull request opened event again
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            1,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .count(),
        )

    @responses.activate
    def test_edit_pull_request_update_env_preview_metadata(self):
        gitapp = self.create_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)

        self.create_and_deploy_redis_docker_service()
        p, _ = self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive pull request opened event again
        pull_data = deepcopy(GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA)
        pull_data["action"] = "edited"
        pull_data["pull_request"]["title"] = "New title"
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=pull_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                pull_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertEqual("New title", preview_env.preview_metadata.pr_title)  # type: ignore

    @responses.activate
    def test_webhook_push_made_on_pull_request_preview_is_ignored(self):
        gitapp = self.create_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive Git push event
        pr_data = GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA["pull_request"]
        push_data = deepcopy(GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        push_data["ref"] = f"refs/heads/{pr_data['head']['ref']}"
        push_data["repository"]["full_name"] = pr_data["head"]["repo"]["full_name"]

        github = cast(GitHubApp, gitapp.github)
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=push_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PUSH,
                push_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)

        cloned_service = preview_env.services.get(slug="fredkiss-dev")
        self.assertEqual(1, cloned_service.deployments.count())

    @responses.activate
    def test_webhook_pr_synchronize_redeploy_service(self):
        gitapp = self.create_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive pull request synchronize event
        pull_data = deepcopy(GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA)
        pull_data["action"] = "synchronize"

        github = cast(GitHubApp, gitapp.github)
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=pull_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                pull_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)

        cloned_service = preview_env.services.get(slug="fredkiss-dev")
        self.assertEqual(2, cloned_service.deployments.count())

    @responses.activate
    async def test_webhook_pr_synchronize_redeploy_service_and_create_resources(self):
        gitapp = await self.acreate_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            await p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .afirst(),
        )
        self.assertIsNotNone(preview_env)

        cloned_service = await preview_env.services.aget(slug="fredkiss-dev")
        first_production = await cloned_service.alatest_production_deployment

        # receive pull request synchronize event
        pull_data = deepcopy(GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA)
        pull_data["action"] = "synchronize"

        github = cast(GitHubApp, gitapp.github)
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=pull_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                pull_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(2, await cloned_service.deployments.acount())

        latest_production = cast(
            Deployment, await cloned_service.alatest_production_deployment
        )
        self.assertNotEqual(first_production, latest_production)

        swarm_service = self.fake_docker_client.get_deployment_service(
            latest_production
        )
        self.assertIsNotNone(swarm_service)

        service_images = self.fake_docker_client.images_list(
            filters={"label": [f"parent={cloned_service.id}"]}  # type: ignore
        )
        self.assertEqual(1, len(service_images))

    @responses.activate
    async def test_close_pull_request_should_delete_preview_env(self):
        gitapp = await self.acreate_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            await p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .afirst(),
        )
        self.assertIsNotNone(preview_env)

        # receive pull request close event
        pull_data = deepcopy(GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA)
        pull_data["action"] = "closed"
        pull_data["pull_request"]["state"] = "closed"

        github = cast(GitHubApp, gitapp.github)
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=pull_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                pull_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            0,
            await p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .acount(),
        )

        archived_env = await ArchivedEnvironment.objects.filter(
            name=preview_env.name
        ).afirst()
        self.assertIsNotNone(archived_env)
        self.assertEqual(0, await p.environments.filter(is_preview=True).acount())
        self.assertEqual(0, await PreviewEnvMetadata.objects.acount())
        self.assertEqual(2, await p.services.acount())
        network = self.fake_docker_client.get_env_network(preview_env)
        self.assertIsNone(network)

    @responses.activate
    async def test_fork_prs_should_require_approval_and_not_deploy_anything(self):
        gitapp = await self.acreate_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="pokedex",
            repository="https://github.com/Fredkiss3/simple-pokedex",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            await p.environments.filter(is_preview=True)
            .select_related(
                "preview_metadata",
                "preview_metadata__service",
                "preview_metadata__git_app",
            )
            .afirst(),
        )
        self.assertIsNotNone(preview_env)
        preview_meta = cast(PreviewEnvMetadata, preview_env.preview_metadata)
        self.assertIsNotNone(preview_meta)

        pr_data = GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK["pull_request"]

        self.assertTrue(
            preview_env.name.startswith(
                f"preview-pr-{pr_data['number']}-{service.slug}"
            )
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(pr_data["head"]["ref"], preview_meta.branch_name)
        repo_url = "https://github.com/" + pr_data["head"]["repo"]["full_name"] + ".git"
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(
            pr_data["html_url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.PENDING,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            pr_data["number"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            pr_data["title"],
            preview_meta.pr_title,
        )

        self.assertEqual(service, preview_meta.service)
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(gitapp, preview_meta.git_app)
        self.assertEqual("HEAD", preview_meta.commit_sha)

        self.assertEqual(2, await preview_env.services.acount())

        self.assertEqual(
            0,
            await Deployment.objects.filter(
                service__environment__name=preview_env.name
            ).acount(),
        )

        self.assertGreater(
            await DeploymentChange.objects.filter(
                service__environment__name=preview_env.name, applied=False
            ).acount(),
            0,
        )
        network = self.fake_docker_client.get_env_network(preview_env)
        self.assertIsNone(network)

    @responses.activate
    async def test_fork_prs_approve_should_deploy_env(self):
        gitapp = await self.acreate_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="pokedex",
            repository="https://github.com/Fredkiss3/simple-pokedex",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            await p.environments.filter(is_preview=True)
            .select_related(
                "preview_metadata",
                "preview_metadata__service",
                "preview_metadata__git_app",
            )
            .afirst(),
        )
        self.assertIsNotNone(preview_env)

        # approve environment deploy
        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.review_deploy",
                kwargs=dict(slug=p.slug, env_slug=preview_env.name),
            ),
            data={"decision": PreviewEnvDeployDecision.ACCEPT},
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        preview_meta = cast(PreviewEnvMetadata, preview_env.preview_metadata)
        await preview_meta.arefresh_from_db()
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.APPROVED, preview_meta.deploy_state
        )

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
        git_service = await preview_env.services.filter(
            type=Service.ServiceType.GIT_REPOSITORY
        ).afirst()
        docker_service = await preview_env.services.filter(
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
    async def test_fork_prs_declined_should_delete_preview_env(self):
        self.assertFalse(True)

    @responses.activate
    async def test_do_not_deploy_preview_env_on_fork_prs_on_pr_sync_if_not_approved(
        self,
    ):
        gitapp = await self.acreate_and_install_github_app()
        github = cast(GitHubApp, gitapp.github)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="pokedex",
            repository="https://github.com/Fredkiss3/simple-pokedex",
            git_app_id=gitapp.id,
        )

        # receive pull request opened event
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive pull request synchronize event
        pull_data = deepcopy(GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK)
        pull_data["action"] = "synchronize"

        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=pull_data,
            headers=get_github_signed_event_headers(
                GithubWebhookEvent.PULL_REQUEST,
                pull_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            await p.environments.filter(is_preview=True)
            .select_related(
                "preview_metadata",
                "preview_metadata__service",
                "preview_metadata__git_app",
            )
            .afirst(),
        )
        self.assertIsNotNone(preview_env)
        preview_meta = cast(PreviewEnvMetadata, preview_env.preview_metadata)
        self.assertIsNotNone(preview_meta)

        pr_data = GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA_FOR_FORK["pull_request"]

        self.assertTrue(
            preview_env.name.startswith(
                f"preview-pr-{pr_data['number']}-{service.slug}"
            )
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(pr_data["head"]["ref"], preview_meta.branch_name)
        repo_url = "https://github.com/" + pr_data["head"]["repo"]["full_name"] + ".git"
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(
            pr_data["html_url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.PENDING,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            pr_data["number"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            pr_data["title"],
            preview_meta.pr_title,
        )

        self.assertEqual(service, preview_meta.service)
        self.assertEqual(repo_url, preview_meta.repository_url)
        self.assertEqual(gitapp, preview_meta.git_app)
        self.assertEqual("HEAD", preview_meta.commit_sha)

        self.assertEqual(2, await preview_env.services.acount())

        self.assertEqual(
            0,
            await Deployment.objects.filter(
                service__environment__name=preview_env.name
            ).acount(),
        )

        self.assertGreater(
            await DeploymentChange.objects.filter(
                service__environment__name=preview_env.name, applied=False
            ).acount(),
            0,
        )
        network = self.fake_docker_client.get_env_network(preview_env)
        self.assertIsNone(network)
