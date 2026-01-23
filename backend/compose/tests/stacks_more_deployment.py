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
    def test_rollback_to_previous_deployment_creates_compose_content_change(self):
        """Rolling back should create a change for the compose content to match the target deployment"""
        # Deploy initial stack
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        first_deployment = cast(
            ComposeStackDeployment,
            stack.deployments.order_by("queued_at").first(),
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
        response = self.client.put(
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
        response = self.client.put(
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

        stack.refresh_from_db()
        self.assertEqual(2, stack.deployments.count())

        # Rollback to first deployment
        response = self.client.put(
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
        stack.refresh_from_db()
        self.assertEqual(3, stack.deployments.count())

        latest_deployment = cast(
            ComposeStackDeployment, stack.deployments.latest("queued_at")
        )
        self.assertEqual(
            1,
            latest_deployment.changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
            ).count(),
        )

        # Verify the compose content is reverted to the first deployment's content
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), stack.user_content)

    def test_rollback_to_previous_deployment_creates_env_override_changes(self):
        """Rolling back should create changes for env overrides to match the target deployment"""
        # Deploy initial stack with env overrides
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES
        )

        first_deployment = cast(
            ComposeStackDeployment,
            stack.deployments.order_by("queued_at").first(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Get initial env override count
        initial_env_count = stack.env_overrides.count()
        self.assertEqual(2, initial_env_count)

        payload = {
            "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
            "type": ComposeStackChange.ChangeType.ADD,
            "new_value": {
                "key": "NEW_ENV_VAR",
                "value": "new_value",
            },
        }

        # Add a new env override
        response = self.client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data=payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the stack with new env override
        response = self.client.put(
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

        stack.refresh_from_db()
        self.assertEqual(2, stack.deployments.count())

        # Verify the new env was added
        self.assertEqual(3, stack.env_overrides.count())

        # Rollback to first deployment
        response = self.client.put(
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

        # Verify the env override count is back to initial
        stack.refresh_from_db()
        self.assertEqual(3, stack.deployments.count())
        self.assertEqual(initial_env_count, stack.env_overrides.count())

        # Verify the `NEW_ENV_VAR` was removed
        new_env = stack.env_overrides.filter(key="NEW_ENV_VAR").first()
        self.assertIsNone(new_env)

        # check that the change has been created correctly
        latest_deployment = cast(
            ComposeStackDeployment, stack.deployments.latest("queued_at")
        )
        self.assertEqual(
            1,
            latest_deployment.changes.filter(
                field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
                type=ComposeStackChange.ChangeType.DELETE,
            ).count(),
        )

    def test_rollback_to_previous_deployment_reverts_updated_env_override(self):
        """Rolling back should revert an updated env override to its previous value"""
        # Deploy initial stack with env overrides
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES
        )

        first_deployment = cast(
            ComposeStackDeployment,
            stack.deployments.order_by("queued_at").first(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Get an existing env override
        env_override = cast(
            ComposeStackEnvOverride,
            stack.env_overrides.first(),
        )
        self.assertIsNotNone(env_override)
        original_value = env_override.value
        env_override_id = env_override.id

        payload = {
            "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
            "type": ComposeStackChange.ChangeType.UPDATE,
            "item_id": env_override_id,
            "new_value": {
                "key": env_override.key,
                "value": "updated_value_12345",
            },
        }
        # Update the env override
        response = self.client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data=payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the stack with updated env override
        response = self.client.put(
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
        env_override.refresh_from_db()
        self.assertEqual("updated_value_12345", env_override.value)

        # Rollback to first deployment
        response = self.client.put(
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

        # Verify the env override value is reverted
        env_override.refresh_from_db()
        self.assertEqual(original_value, env_override.value)

        # check that the change has been created correctly
        latest_deployment = cast(
            ComposeStackDeployment, stack.deployments.latest("queued_at")
        )
        self.assertEqual(
            1,
            latest_deployment.changes.filter(
                field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).count(),
        )

    def test_rollback_to_same_deployment_no_changes(self):
        """Rolling back to the same deployment (current state) should create a deployment with no actual changes"""
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        first_deployment = cast(
            ComposeStackDeployment,
            stack.deployments.order_by("queued_at").first(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Rollback to the same (and only) deployment
        response = self.client.put(
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

        # A new deployment should still be created (redeploy always triggers a new deployment)
        stack.refresh_from_db()
        self.assertEqual(2, stack.deployments.count())

        # check that no changes have been created
        latest_deployment = cast(
            ComposeStackDeployment, stack.deployments.latest("queued_at")
        )
        self.assertEqual(
            0,
            latest_deployment.changes.count(),
        )

    def test_rollback_sets_is_redeploy_of_field(self):
        """Rolling back should set the is_redeploy_of field on the new deployment"""
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        first_deployment = cast(
            ComposeStackDeployment,
            stack.deployments.order_by("queued_at").first(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Update and deploy to have something to rollback from
        response = self.client.put(
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

        response = self.client.put(
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
        response = self.client.put(
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
        self.assertIn("redeploy_hash", response_data)
        self.assertEqual(first_deployment_hash, response_data["redeploy_hash"])

    async def test_rollback_recreates_docker_services(self):
        """Rolling back should recreate docker services that were removed after the target deployment"""
        # Deploy initial stack with two services
        initial_content = """
services:
  redis:
    image: valkey/valkey:alpine
  nginx:
    image: nginx:alpine
"""
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=initial_content
        )

        first_deployment = cast(
            ComposeStackDeployment,
            await stack.deployments.order_by("queued_at").afirst(),
        )
        self.assertIsNotNone(first_deployment)
        first_deployment_hash = first_deployment.hash

        # Verify initial docker services are created
        initial_services = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        initial_service_names = {s.name for s in initial_services}
        self.assertEqual(2, len(initial_services))

        # Update compose content to remove nginx service
        updated_content = """
services:
  redis:
    image: valkey/valkey:alpine
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

        # Deploy the updated stack (nginx removed)
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

        # Verify nginx service was removed
        services_after_update = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        self.assertEqual(1, len(services_after_update))

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

        # Verify docker services are recreated
        await stack.arefresh_from_db()
        self.assertEqual(3, await stack.deployments.acount())

        services_after_rollback = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        self.assertEqual(2, len(services_after_rollback))

        # Verify service names match the initial deployment
        rollback_service_names = {s.name for s in services_after_rollback}
        self.assertEqual(initial_service_names, rollback_service_names)
