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
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WEB_WITH_DB,
    INVALID_COMPOSE_NO_IMAGE,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
)
from .stacks import ComposeStackAPITestBase
import responses
from django.conf import settings
import requests
from temporal.helpers import ZaneProxyClient
from compose.dtos import ComposeStackUrlRouteDto


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


class TestArchiveProjectWithStackViewTests(ComposeStackAPITestBase):
    def test_delete_project_should_delete_included_stacks(self):
        p, stack = self.create_and_deploy_compose_stack(content=DOCKER_COMPOSE_MINIMAL)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(0, ComposeStack.objects.filter(pk=stack.id).count())

    async def test_delete_project_should_delete_included_stack_resources(self):
        p, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        stack_name = stack.name

        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(0, await ComposeStack.objects.filter(project_id=p.id).acount())

        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(service_list))

    @responses.activate()
    async def test_archive_project_delete_stack_urls_in_proxy(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE
        )

        stack_id = stack.id
        # Get route info before archiving
        routes = stack.urls["web"]  # type: ignore
        route = cast(dict, routes[0])

        # Verify route is registered in Caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(200, response.status_code)

        # delete project
        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # delete project
        self.assertEqual(0, await ComposeStack.objects.filter(project_id=p.id).acount())

        # Verify route is removed from Caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack_id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(404, response.status_code)

    @responses.activate()
    async def test_archive_project_delete_stack_configs(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_INLINE_CONFIGS
        )

        stack_name = stack.name

        # Verify config stack exists
        config_list = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(1, len(config_list))

        # delete project
        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify config stack is deleted
        config_list = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(config_list))

    @responses.activate()
    async def test_archive_project_delete_stack_volumes(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_SIMPLE_DB
        )

        stack_name = stack.name

        # Verify Docker volumes exist
        volumes = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(1, len(volumes))

        # delete project
        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify Docker volumes are removed
        volumes = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(volumes))


class TestArchiveEnvironmentWithStackViewTests(ComposeStackAPITestBase):
    async def acreate_and_deploy_compose_stack_in_environment(
        self,
        content: str,
        environment: str = "staging",
        slug="my-stack",
    ):
        project = await self.acreate_project(slug="compose")

        create_env_payload = {
            "name": environment,
        }

        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.create",
                kwargs={
                    "slug": project.slug,
                },
            ),
            data=create_env_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        create_stack_payload = {
            "slug": slug,
            "user_content": content,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": environment,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack, await ComposeStack.objects.filter(slug=slug).afirst()
        )
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.user_content)
        self.assertIsNone(stack.computed_content)

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": environment,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await stack.arefresh_from_db()

        env = await project.environments.aget(name=environment)
        return project, stack, env

    async def test_delete_environment_should_delete_included_stacks(self):
        p, stack, env = await self.acreate_and_deploy_compose_stack_in_environment(
            content=DOCKER_COMPOSE_MINIMAL
        )

        self.assertEqual(
            1, await ComposeStack.objects.filter(environment_id=env.id).acount()
        )

        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": p.slug,
                    "env_slug": env.name,
                },
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0, await ComposeStack.objects.filter(environment_id=env.id).acount()
        )

    async def test_delete_environment_should_delete_included_stack_resources(self):
        p, stack, env = await self.acreate_and_deploy_compose_stack_in_environment(
            content=DOCKER_COMPOSE_MINIMAL
        )

        stack_name = stack.name
        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(1, len(service_list))

        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": p.slug,
                    "env_slug": env.name,
                },
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0, await ComposeStack.objects.filter(environment_id=env.id).acount()
        )

        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(service_list))

    @responses.activate()
    async def test_archive_environment_delete_stack_urls_in_proxy(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, stack, env = await self.acreate_and_deploy_compose_stack_in_environment(
            content=DOCKER_COMPOSE_WEB_SERVICE
        )

        stack_id = stack.id
        # Get route info before archiving
        routes = stack.urls["web"]  # type: ignore
        route = cast(dict, routes[0])

        # Verify route is registered in Caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(200, response.status_code)

        # delete environment
        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": p.slug,
                    "env_slug": env.name,
                },
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # delete project
        self.assertEqual(0, await ComposeStack.objects.filter(project_id=p.id).acount())

        # Verify route is removed from Caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack_id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(404, response.status_code)

    @responses.activate()
    async def test_archive_environment_delete_stack_configs(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, stack, env = await self.acreate_and_deploy_compose_stack_in_environment(
            content=DOCKER_COMPOSE_WITH_INLINE_CONFIGS
        )

        stack_name = stack.name

        # Verify config stack exists
        config_list = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(1, len(config_list))

        # delete environment
        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": p.slug,
                    "env_slug": env.name,
                },
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify config stack is deleted
        config_list = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(config_list))

    @responses.activate()
    async def test_archive_environment_delete_stack_volumes(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, stack, env = await self.acreate_and_deploy_compose_stack_in_environment(
            content=DOCKER_COMPOSE_SIMPLE_DB
        )

        stack_name = stack.name

        # Verify Docker volumes exist
        volumes = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(1, len(volumes))

        # delete environment
        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": p.slug,
                    "env_slug": env.name,
                },
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify Docker volumes are removed
        volumes = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(volumes))


class TestDeployTokenComposeStackViewTests(ComposeStackAPITestBase):
    def test_create_stack_generates_deploy_token(self):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "my-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(ComposeStack, ComposeStack.objects.first())
        self.assertIsNotNone(stack.deploy_token)

    def test_stack_regenerates_deploy_token(self):
        project, stack = self.create_and_deploy_compose_stack(DOCKER_COMPOSE_MINIMAL)

        initial_token = stack.deploy_token

        response = self.client.put(
            reverse(
                "compose:stacks.regenerate_deploy_token",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        stack.refresh_from_db()
        self.assertNotEqual(initial_token, stack.deploy_token)

    def test_deploy_compose_stack_using_token(self):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "my-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        # create stack
        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(ComposeStack, ComposeStack.objects.first())

        # deploy stack using webhook
        response = self.client.put(
            reverse(
                "compose:stacks.webhook_deploy",
                kwargs={"deploy_token": stack.deploy_token},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(1, stack.deployments.count())

    async def test_webhook_deploy_compose_stack_create_resources(self):
        project = await self.acreate_project(slug="compose")

        create_stack_payload = {
            "slug": "my-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        # create stack
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
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(ComposeStack, await ComposeStack.objects.afirst())

        # deploy stack using webhook
        response = await self.async_client.put(
            reverse(
                "compose:stacks.webhook_deploy",
                kwargs={"deploy_token": stack.deploy_token},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(1, await stack.deployments.acount())

        service = None
        try:
            service = self.fake_docker_client.services_get(
                f"{stack.name}_{stack.hash_prefix}_redis"
            )
        except Exception:
            pass
        self.assertIsNotNone(service)

    def test_deploy_compose_stack_using_token_update_user_content(self):
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        # deploy stack using webhook
        deploy_payload = {
            "user_content": DOCKER_COMPOSE_WEB_WITH_DB,
        }
        response = self.client.put(
            reverse(
                "compose:stacks.webhook_deploy",
                kwargs={
                    "deploy_token": stack.deploy_token,
                },
            ),
            data=deploy_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # the user content should have been updated
        stack.refresh_from_db()
        self.assertEqual(DOCKER_COMPOSE_WEB_WITH_DB.strip(), stack.user_content)

        # a change with the new content should be created
        deployment = cast(ComposeStackDeployment, stack.deployments.latest("queued_at"))
        self.assertIsNotNone(deployment)

        content_change = cast(
            ComposeStackChange,
            deployment.changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
            ).first(),
        )
        self.assertIsNotNone(content_change)
        self.assertEqual(DOCKER_COMPOSE_WEB_WITH_DB.strip(), content_change.new_value)

    def test_deploy_compose_stack_using_token_validate_new_user_content(self):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "my-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        # create stack
        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(ComposeStack, ComposeStack.objects.first())

        # deploy stack using webhook
        deploy_payload = {
            "user_content": INVALID_COMPOSE_NO_IMAGE,
        }
        response = self.client.put(
            reverse(
                "compose:stacks.webhook_deploy",
                kwargs={
                    "deploy_token": stack.deploy_token,
                },
            ),
            data=deploy_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))
