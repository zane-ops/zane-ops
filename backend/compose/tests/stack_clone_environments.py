from typing import cast

import docker.errors

from django.urls import reverse
from rest_framework import status
from zane_api.models import Environment
from zane_api.utils import jprint

from ..models import ComposeStack, ComposeStackChange
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_WEB_SERVICE,
)
from .stacks import ComposeStackAPITestBase


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
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), content_change.new_value)

        self.assertEqual(original_stack.slug, cloned_stack.slug)
        self.assertEqual(
            original_stack.network_alias_prefix, cloned_stack.network_alias_prefix
        )
        self.assertNotEqual(original_stack.deploy_token, cloned_stack.deploy_token)

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
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), content_change.new_value)

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
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), cloned_stack.user_content)

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
