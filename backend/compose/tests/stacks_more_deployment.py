from typing import cast

from django.urls import reverse
from rest_framework import status

from zane_api.models import Environment
from zane_api.utils import jprint

from ..models import (
    ComposeStack,
    ComposeStackChange,
    ComposeStackDeployment,
    ComposeStackEnvOverride,
)
from .fixtures import DOCKER_COMPOSE_MINIMAL, DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES
from .stacks import ComposeStackAPITestBase


class ToggleStackSleepViewTests(ComposeStackAPITestBase):
    async def test_stop_stack_scales_all_services_to_zero(self):
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        # Verify stack is deployed and has service statuses
        self.assertIsNotNone(stack.service_statuses)
        statuses = cast(dict, stack.service_statuses)
        self.assertGreater(len(statuses), 0)

        # Stop the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"desired_state": "stop"},
        )
        jprint(response.json() if response.status_code != 202 else None)
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        for service in service_list:
            self.assertEqual(0, service.replicas)

    async def test_start_stack_scales_all_services_back(self):
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        # First stop the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"desired_state": "stop"},
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        for service in service_list:
            self.assertEqual(service.replicas, 0)

        # Then start it back
        response = await self.async_client.put(
            reverse(
                "compose:stacks.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"desired_state": "start"},
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        for service in service_list:
            self.assertGreater(service.replicas, 0)

    async def test_cannot_toggle_stack_without_deployment(self):
        project = await self.acreate_project(slug="compose")

        # Create stack but don't deploy it
        create_stack_payload = {
            "slug": "undeployed-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="undeployed-stack").afirst(),
        )
        self.assertIsNotNone(stack)

        # Try to toggle the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"desired_state": "stop"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)


class RollBackStackViewTests(ComposeStackAPITestBase):
    async def test_rollback_to_previous_deployment_creates_compose_content_change(self):
        """Rolling back should create a change for the compose content to match the target deployment"""
        # Deploy initial stack
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        first_deployment = cast(
            ComposeStackDeployment,
            await stack.deployments.order_by("queued_at").afirst(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Update compose content and deploy again
        updated_content = """
services:
  redis:
    image: valkey/valkey:alpine
  nginx:
    image: nginx:alpine
"""
        response = await self.async_client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={
                "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                "type": ComposeStackChange.ChangeType.UPDATE,
                "new_value": updated_content,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the updated stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await stack.arefresh_from_db()
        self.assertEqual(2, await stack.deployments.acount())

        # Rollback to first deployment
        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": first_deployment_hash,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify that changes were applied
        await stack.arefresh_from_db()
        self.assertEqual(3, await stack.deployments.acount())

        latest_deployment = cast(
            ComposeStackDeployment, await stack.deployments.alatest("-queued_at")
        )
        self.assertEqual(1, latest_deployment.changes.acount())
        self.assertEqual(
            1,
            latest_deployment.changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
            ).acount(),
        )

        # Verify the compose content is reverted to the first deployment's content
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), stack.user_content)

    async def test_rollback_to_previous_deployment_creates_env_override_changes(self):
        """Rolling back should create changes for env overrides to match the target deployment"""
        # Deploy initial stack with env overrides
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES
        )

        first_deployment = cast(
            ComposeStackDeployment,
            await stack.deployments.order_by("queued_at").afirst(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Get initial env override count
        initial_env_count = await stack.env_overrides.acount()
        self.assertGreater(initial_env_count, 0)

        # Add a new env override
        response = await self.async_client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={
                "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
                "type": ComposeStackChange.ChangeType.ADD,
                "new_value": {
                    "key": "NEW_ENV_VAR",
                    "value": "new_value",
                },
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the stack with new env override
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await stack.arefresh_from_db()
        self.assertEqual(2, await stack.deployments.acount())

        # Verify the new env was added
        updated_env_count = await stack.env_overrides.acount()
        self.assertEqual(initial_env_count + 1, updated_env_count)

        # Rollback to first deployment
        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": first_deployment_hash,
                },
            ),
        )
        jprint(response.json() if response.status_code != 200 else None)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify the env override count is back to initial
        await stack.arefresh_from_db()
        self.assertEqual(3, await stack.deployments.acount())
        self.assertEqual(initial_env_count, await stack.env_overrides.acount())

        # Verify the NEW_ENV_VAR was removed
        new_env = await stack.env_overrides.filter(key="NEW_ENV_VAR").afirst()
        self.assertIsNone(new_env)

    async def test_rollback_to_previous_deployment_reverts_updated_env_override(self):
        """Rolling back should revert an updated env override to its previous value"""
        # Deploy initial stack with env overrides
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES
        )

        first_deployment = cast(
            ComposeStackDeployment,
            await stack.deployments.order_by("queued_at").afirst(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Get an existing env override
        env_override = cast(
            ComposeStackEnvOverride,
            await stack.env_overrides.afirst(),
        )
        self.assertIsNotNone(env_override)
        original_value = env_override.value
        env_override_id = env_override.id

        # Update the env override
        response = await self.async_client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={
                "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
                "type": ComposeStackChange.ChangeType.UPDATE,
                "item_id": env_override_id,
                "new_value": {
                    "key": env_override.key,
                    "value": "updated_value_12345",
                },
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the stack with updated env override
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify the env was updated
        await env_override.arefresh_from_db()
        self.assertEqual("updated_value_12345", env_override.value)

        # Rollback to first deployment
        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": first_deployment_hash,
                },
            ),
        )
        jprint(response.json() if response.status_code != 200 else None)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify the env override value is reverted
        await env_override.arefresh_from_db()
        self.assertEqual(original_value, env_override.value)

    async def test_rollback_nonexistent_deployment_returns_404(self):
        """Rolling back to a non-existent deployment should return 404"""
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": "stk_dpl_nonexistent",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_rollback_nonexistent_stack_returns_404(self):
        """Rolling back on a non-existent stack should return 404"""
        project = await self.acreate_project(slug="compose")

        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": "nonexistent-stack",
                    "hash": "stk_dpl_hash123",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_rollback_nonexistent_project_returns_404(self):
        """Rolling back on a non-existent project should return 404"""
        await self.aLoginUser()

        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": "nonexistent-project",
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": "some-stack",
                    "hash": "stk_dpl_hash123",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_rollback_to_same_deployment_no_changes(self):
        """Rolling back to the same deployment (current state) should create a deployment with no actual changes"""
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        first_deployment = cast(
            ComposeStackDeployment,
            await stack.deployments.order_by("queued_at").afirst(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Rollback to the same (and only) deployment
        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": first_deployment_hash,
                },
            ),
        )
        jprint(response.json() if response.status_code != 200 else None)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # A new deployment should still be created (redeploy always triggers a new deployment)
        await stack.arefresh_from_db()
        self.assertEqual(2, await stack.deployments.acount())

    async def test_rollback_sets_is_redeploy_of_field(self):
        """Rolling back should set the is_redeploy_of field on the new deployment"""
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        first_deployment = cast(
            ComposeStackDeployment,
            await stack.deployments.order_by("queued_at").afirst(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Update and deploy to have something to rollback from
        response = await self.async_client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={
                "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                "type": ComposeStackChange.ChangeType.UPDATE,
                "new_value": """
services:
  redis:
    image: redis:7-alpine
""",
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Rollback to first deployment
        response = await self.async_client.put(
            reverse(
                "compose:stacks.redeploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": first_deployment_hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        response_data = response.json()

        # The response should indicate this is a redeploy
        self.assertIn("is_redeploy_of", response_data)
        self.assertEqual(first_deployment_hash, response_data["is_redeploy_of"])
