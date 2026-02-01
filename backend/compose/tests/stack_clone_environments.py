from typing import cast

import docker.errors

from django.urls import reverse
import responses
from rest_framework import status
from zane_api.models import Environment, PreviewEnvTemplate
from zane_api.utils import jprint

from ..models import ComposeStack, ComposeStackChange, ComposeStackEnvOverride
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES,
    DOCKER_COMPOSE_WITH_GENERATE_DOMAIN,
)
from .stacks import ComposeStackAPITestBase
import yaml
from zane_api.tests.preview_environments import BasePreviewEnvTests
from git_connectors.models import GitHubApp, GitlabApp
from git_connectors.tests.fixtures import (
    GITHUB_PULL_REQUEST_WEBHOOK_EVENT_DATA,
    GITLAB_MERGE_REQUEST_WEBHOOK_EVENT_DATA,
    mock_github_comments_api,
    get_github_signed_event_headers,
    mock_gitlab_notes_api,
)
from git_connectors.serializers.github import GithubWebhookEvent
from git_connectors.serializers.gitlab import GitlabWebhookEvent


class CloneEnvironmentWithStackViewTests(ComposeStackAPITestBase):
    def test_clone_environment_should_clone_included_stacks(self):
        p, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={"name": "staging"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, stacks_in_staging.count())

        cloned_stack = cast(ComposeStack, stacks_in_staging.first())

        self.assertEqual(1, cloned_stack.unapplied_changes.count())

        content_change = cast(
            ComposeStackChange,
            cloned_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
            ).first(),
        )
        self.assertIsNotNone(content_change)
        self.assertEqual(
            yaml.safe_dump(yaml.safe_load(DOCKER_COMPOSE_MINIMAL), sort_keys=False),
            content_change.new_value,
        )

        self.assertEqual(original_stack.slug, cloned_stack.slug)
        self.assertEqual(
            original_stack.network_alias_prefix, cloned_stack.network_alias_prefix
        )
        self.assertNotEqual(original_stack.deploy_token, cloned_stack.deploy_token)

    def test_clone_environment_with_environment_overrides(self):
        p, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={
                "name": "staging",
                "deploy_after_clone": True,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, stacks_in_staging.count())

        cloned_stack = cast(ComposeStack, stacks_in_staging.first())

        self.assertEqual(2, cloned_stack.env_overrides.count())

        for env in original_stack.env_overrides.all():
            cloned_env = cast(
                ComposeStackEnvOverride,
                cloned_stack.env_overrides.filter(key=env.key).first(),
            )
            self.assertIsNotNone(cloned_env)
            self.assertEqual(
                env.value, cloned_env.value, f"envs `{env.key}` do not match"
            )

    def test_clone_environment_with_generate_domain_override_is_not_passed_directly(
        self,
    ):
        p, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_GENERATE_DOMAIN
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={
                "name": "staging",
                "deploy_after_clone": True,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, stacks_in_staging.count())

        cloned_stack = cast(ComposeStack, stacks_in_staging.first())

        self.assertEqual(1, cloned_stack.env_overrides.count())

        print(
            "========= original =========",
            original_stack.user_content,
            sep="\n",
        )
        print(
            "========= cloned =========",
            cloned_stack.user_content,
            sep="\n",
        )

        original_env = original_stack.env_overrides.get(key="APP_DOMAIN")
        # `APP_DOMAIN` should be regenerated
        cloned_env = cloned_stack.env_overrides.get(key="APP_DOMAIN")

        self.assertNotEqual(original_env.value, cloned_env.value)

    def test_clone_environment_with_undeployed_stacks_should_include_unapplied_changes_in_diffing(
        self,
    ):
        p, _ = self.create_compose_stack(content=DOCKER_COMPOSE_MINIMAL)

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={"name": "staging"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, stacks_in_staging.count())

        stack = cast(ComposeStack, stacks_in_staging.first())

        self.assertEqual(1, stack.unapplied_changes.count())

        content_change = cast(
            ComposeStackChange,
            stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
            ).first(),
        )
        self.assertIsNotNone(content_change)
        self.assertEqual(
            yaml.safe_dump(yaml.safe_load(DOCKER_COMPOSE_MINIMAL), sort_keys=False),
            content_change.new_value,
        )

    async def test_clone_environment_with_deploy_true_should_deploy_included_stacks(
        self,
    ):
        p, original_stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={"name": "staging", "deploy_after_clone": True},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = await p.environments.aget(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, await stacks_in_staging.acount())

        cloned_stack = cast(ComposeStack, await stacks_in_staging.afirst())
        self.assertIsNotNone(cloned_stack)

        # user content change has been applied
        self.assertEqual(
            yaml.safe_dump(yaml.safe_load(DOCKER_COMPOSE_MINIMAL), sort_keys=False),
            cloned_stack.user_content,
        )

        self.assertEqual(1, await cloned_stack.deployments.acount())

        service = None
        try:
            service = self.fake_docker_client.services_get(
                f"{cloned_stack.name}_{cloned_stack.hash_prefix}_redis"
            )
        except Exception:
            pass
        self.assertIsNotNone(service)

    async def test_clone_environment_deploy_false_should_not_deploy_included_stacks(
        self,
    ):
        p, _ = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={"name": "staging"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = await p.environments.aget(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, await stacks_in_staging.acount())

        cloned_stack = cast(ComposeStack, await stacks_in_staging.afirst())

        self.assertEqual(0, await cloned_stack.deployments.acount())

        with self.assertRaises(docker.errors.NotFound):
            self.fake_docker_client.services_get(
                f"{cloned_stack.name}_{cloned_stack.hash_prefix}_redis"
            )


class CloneEnvironmentWithStackURLsViewTests(ComposeStackAPITestBase):
    def test_clone_environment_with_urls_replace_urls_with_generated_ones_in_compose_content(
        self,
    ):
        p, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV_NAME},
            ),
            data={"name": "staging", "deploy_after_clone": True},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        stacks_in_staging = staging_env.compose_stacks
        self.assertEqual(1, stacks_in_staging.count())

        cloned_stack = cast(ComposeStack, stacks_in_staging.first())

        self.assertIsNotNone(cloned_stack.user_content)
        self.assertNotIn(
            "hello.127-0-0-1.sslip.io", cast(str, cloned_stack.user_content)
        )

        print(
            "========= original =========",
            original_stack.user_content,
            sep="\n",
        )
        print(
            "========= cloned =========",
            cloned_stack.user_content,
            sep="\n",
        )

        # it should create an env override in compose stack file
        self.assertIn("x-zane-env", cast(str, cloned_stack.user_content))
        self.assertIn("{{ generate_domain }}", cast(str, cloned_stack.user_content))


class CloneEnvironmentViaPreviewTrigger(BasePreviewEnvTests, ComposeStackAPITestBase):
    @responses.activate
    def test_clone_env_via_preview_clone_stacks_in_preview(self):
        gitapp = self.create_and_install_github_app()

        # Deploy git service & compose stack
        p, service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        _, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL,
            project=p,
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

        stacks_in_preview = preview_env.compose_stacks
        self.assertEqual(1, stacks_in_preview.count())

        cloned_stack = cast(ComposeStack, stacks_in_preview.first())

        # user content change has been applied
        self.assertIsNotNone(cloned_stack.user_content)

        # stack has been deployed
        self.assertGreater(cloned_stack.deployments.count(), 0)

    @responses.activate
    def test_clone_env_via_preview_with_ignored_stacks_in_template_do_not_clone_those_stacks(
        self,
    ):
        gitapp = self.create_and_install_github_app()

        # Deploy git service & compose stack
        p, service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        _, ignored_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL, project=p, slug="ignored"
        )

        _, included_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL, project=p, slug="included"
        )

        template = p.default_preview_template
        template.clone_strategy = PreviewEnvTemplate.PreviewCloneStrategy.ONLY
        template.stacks_to_clone.add(included_stack)
        template.save()

        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-1"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True)
            .select_related("preview_metadata")
            .first(),
        )
        self.assertIsNotNone(preview_env)

        stacks_in_preview = preview_env.compose_stacks
        self.assertEqual(1, stacks_in_preview.count())

        self.assertIsNotNone(stacks_in_preview.filter(slug=included_stack.slug).first())
        self.assertIsNone(stacks_in_preview.filter(slug=ignored_stack.slug).first())

    @responses.activate
    def test_clone_env_via_github_pull_request_deploy_compose_stack(self):
        mock_github_comments_api()
        gitapp = self.create_and_install_github_app()

        github = cast(GitHubApp, gitapp.github)

        # Deploy git service & compose stack
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://github.com/Fredkiss3/fredkiss.dev",
            git_app_id=gitapp.id,
        )

        _, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL,
            project=p,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)

        stacks_in_preview = preview_env.compose_stacks
        self.assertEqual(1, stacks_in_preview.count())

        cloned_stack = cast(ComposeStack, stacks_in_preview.first())

        # user content change has been applied
        self.assertIsNotNone(cloned_stack.user_content)

        # stack has been deployed
        self.assertGreater(cloned_stack.deployments.count(), 0)

    @responses.activate
    def test_clone_env_via_gitlab_merge_request_deploy_compose_stack(self):
        mock_gitlab_notes_api()
        gitapp = self.create_gitlab_app()

        gitlab = cast(GitlabApp, gitapp.gitlab)

        # Deploy git service & compose stack
        p, service = self.create_and_deploy_git_service(
            slug="fredkiss-dev",
            repository="https://gitlab.com/fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )

        _, original_stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL,
            project=p,
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
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)

        stacks_in_preview = preview_env.compose_stacks
        self.assertEqual(1, stacks_in_preview.count())

        cloned_stack = cast(ComposeStack, stacks_in_preview.first())

        # user content change has been applied
        self.assertIsNotNone(cloned_stack.user_content)

        # stack has been deployed
        self.assertGreater(cloned_stack.deployments.count(), 0)
