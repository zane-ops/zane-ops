import json
import re
from typing import cast

import responses
from ..serializers.gitlab import GitlabWebhookEvent
from zane_api.tests.base import AuthAPITestCase
from .fixtures import (
    GITLAB_PROJECT_LIST,
    GITLAB_ACCESS_TOKEN_DATA,
    GITLAB_PROJECT_WEBHOOK_API_DATA,
    GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
    GITLAB_PUSH_WEBHOOK_EVENT_DATA,
)

from urllib.parse import urlencode

from copy import deepcopy
from asgiref.sync import sync_to_async
from rest_framework import status
from zane_api.utils import generate_random_chars, jprint
from ..models import GitHubApp, GitlabApp
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


class BaseGitlabMergeRequestViewTestCase(AuthAPITestCase):
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
        return await sync_to_async(self.create_gitlab_app)(with_webhook)


class CreateGitlabMergeRequestPreviewEnvGitlabViewTests(
    BaseGitlabMergeRequestViewTestCase
):

    @responses.activate
    def test_open_merge_request_should_create_preview_env(self):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitlabApp, gitapp.gitlab)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
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

        mr_data = GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA["object_attributes"]
        event_data = GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA

        self.assertTrue(
            preview_env.name.startswith(f"preview-mr-{mr_data['iid']}-{service.slug}")
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(mr_data["source_branch"], preview_meta.branch_name)
        repo_url = mr_data["source"]["git_http_url"]
        self.assertEqual(repo_url, preview_meta.head_repository_url)
        self.assertEqual(
            mr_data["url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.APPROVED,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            mr_data["iid"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            mr_data["title"],
            preview_meta.pr_title,
        )
        self.assertEqual(
            event_data["user"]["username"],
            preview_meta.pr_author,
        )
        self.assertEqual(
            mr_data["target"]["git_http_url"],
            preview_meta.pr_base_repo_url,
        )
        self.assertEqual(
            mr_data["target_branch"],
            preview_meta.pr_base_branch_name,
        )
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_meta.template
        )
        self.assertEqual(service, preview_meta.service)
        self.assertEqual(gitapp, preview_meta.git_app)
        self.assertEqual("HEAD", preview_meta.commit_sha)

        self.assertEqual(2, preview_env.services.count())

    @responses.activate
    async def test_open_merge_request_should_deploy_services_in_new_preview_env(self):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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
    def test_open_merge_request_twice_is_idempotent(self):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)

        self.create_and_deploy_redis_docker_service()
        p, _ = self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive merge request opened event again
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            1,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .count(),
        )

    @responses.activate
    def test_edit_merge_request_update_env_preview_metadata(self):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)

        self.create_and_deploy_redis_docker_service()
        p, _ = self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive merge request edited event
        merge_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)
        merge_data["object_attributes"]["action"] = "update"
        merge_data["object_attributes"]["title"] = "New title"
        merge_data["object_attributes"]["target_branch"] = "develop"
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=merge_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertEqual("New title", preview_env.preview_metadata.pr_title)  # type: ignore
        self.assertEqual("develop", preview_env.preview_metadata.pr_base_branch_name)  # type: ignore

    @responses.activate
    def test_merge_request_update_event_with_oldrev_update_preview_meta_and_redeploy_services(
        self,
    ):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)

        self.create_and_deploy_redis_docker_service()
        p, _ = self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive merge request edited event
        merge_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)
        merge_data["object_attributes"]["action"] = "update"
        merge_data["object_attributes"]["title"] = "New title"
        merge_data["object_attributes"]["target_branch"] = "develop"
        merge_data["object_attributes"][
            "oldrev"
        ] = "9532d17cf649644ebf0f4ccf95974ba3520ba27c"
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=merge_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertEqual("New title", preview_env.preview_metadata.pr_title)  # type: ignore
        self.assertEqual("develop", preview_env.preview_metadata.pr_base_branch_name)  # type: ignore

        cloned_service = preview_env.services.get(slug="fredkiss-dev")
        self.assertEqual(2, cloned_service.deployments.count())

    @responses.activate
    async def test_merge_request_update_event_with_oldrev_redeploy_services_and_create_resources(
        self,
    ):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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

        # receive merge request update event
        merge_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)
        merge_data["object_attributes"]["action"] = "update"
        merge_data["object_attributes"][
            "oldrev"
        ] = "9532d17cf649644ebf0f4ccf95974ba3520ba27c"
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=merge_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
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
    def test_webhook_push_made_on_merge_request_branch_are_ignored(self):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive push on merge request branch event
        merge_data = GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA["object_attributes"]
        push_data = deepcopy(GITLAB_PUSH_WEBHOOK_EVENT_DATA)
        push_data["ref"] = "ref/heads/" + merge_data["source_branch"]
        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=push_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.PUSH,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        jprint(response.json())
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
    async def test_close_merge_request_should_delete_preview_env(self):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request opened event
        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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
        merge_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)
        merge_data["object_attributes"]["action"] = "close"

        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=merge_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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
    async def test_fork_merge_request_should_require_approval_and_not_deploy_anything(
        self,
    ):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request open event
        event_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)

        merge_request = event_data["object_attributes"]
        merge_request["source"][
            "git_http_url"
        ] = "https://gitlab.com/mohamedcherifh/private-ac"

        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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

        self.assertTrue(
            preview_env.name.startswith(
                f"preview-mr-{merge_request['iid']}-{service.slug}"
            )
        )
        self.assertTrue(
            PreviewEnvMetadata.PreviewSourceTrigger.PULL_REQUEST,
            preview_meta.source_trigger,
        )

        self.assertEqual(merge_request["source_branch"], preview_meta.branch_name)
        repo_url = merge_request["source"]["git_http_url"]
        self.assertEqual(repo_url, preview_meta.head_repository_url)
        self.assertEqual(
            merge_request["url"],
            preview_meta.external_url,
        )
        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.PENDING,
            preview_meta.deploy_state,
        )
        self.assertEqual(
            merge_request["iid"],
            preview_meta.pr_number,
        )
        self.assertEqual(
            merge_request["title"],
            preview_meta.pr_title,
        )

        self.assertEqual(service, preview_meta.service)
        self.assertEqual(repo_url, preview_meta.head_repository_url)
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
    async def test_fork_merge_request_approve_should_deploy_env(self):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request open event
        event_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)

        merge_request = event_data["object_attributes"]
        merge_request["source"][
            "git_http_url"
        ] = "https://gitlab.com/mohamedcherifh/private-ac"

        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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
            data={"decision": PreviewEnvDeployDecision.APPROVE},
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
    async def test_fork_merge_request_declined_should_delete_preview_env(self):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request open event
        event_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)

        merge_request = event_data["object_attributes"]
        merge_request["source"][
            "git_http_url"
        ] = "https://gitlab.com/mohamedcherifh/private-ac"

        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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

        # decline environment deploy
        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.review_deploy",
                kwargs=dict(slug=p.slug, env_slug=preview_env.name),
            ),
            data={"decision": PreviewEnvDeployDecision.DECLINE},
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(await p.environments.filter(is_preview=True).afirst())

    @responses.activate
    async def test_do_not_deploy_preview_env_on_fork_merge_request_on_merge_push_if_not_approved(
        self,
    ):
        gitapp = await self.acreate_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request open event
        event_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)

        merge_request = event_data["object_attributes"]
        merge_request["source"][
            "git_http_url"
        ] = "https://gitlab.com/mohamedcherifh/private-ac"

        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # receive merge request update event
        merge_request["action"] = "update"
        merge_request["oldrev"] = "9532d17cf649644ebf0f4ccf95974ba3520ba27c"

        response = await self.async_client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
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

        self.assertEqual(
            PreviewEnvMetadata.PreviewDeployState.PENDING,
            preview_meta.deploy_state,
        )

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
    def test_webhook_approved_fork_merge_request_push_should_redeploy_service(self):
        gitapp = self.create_gitlab_app()
        gitlab = cast(GitHubApp, gitapp.gitlab)
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        # receive merge request open event
        event_data = deepcopy(GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA)

        merge_request = event_data["object_attributes"]
        merge_request["source"][
            "git_http_url"
        ] = "https://gitlab.com/mohamedcherifh/private-ac"

        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)

        # approve environment deploy
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.review_deploy",
                kwargs=dict(slug=p.slug, env_slug=preview_env.name),
            ),
            data={"decision": PreviewEnvDeployDecision.APPROVE},
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # receive merge request update event
        merge_request["action"] = "update"
        merge_request["oldrev"] = "9532d17cf649644ebf0f4ccf95974ba3520ba27c"

        response = self.client.post(
            reverse("git_connectors:gitlab.webhook"),
            data=event_data,
            headers={
                "X-Gitlab-Event": GitlabWebhookEvent.MERGE_REQUEST,
                "X-Gitlab-Token": gitlab.webhook_secret,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        cloned_service = preview_env.services.get(slug=service.slug)
        self.assertEqual(2, cloned_service.deployments.count())
