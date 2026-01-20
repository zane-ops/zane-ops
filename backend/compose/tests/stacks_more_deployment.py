from typing import cast

from django.urls import reverse
from rest_framework import status

from zane_api.models import Environment
from zane_api.utils import jprint

from ..models import ComposeStack
from .fixtures import DOCKER_COMPOSE_MINIMAL
from .stacks import ComposeStackAPITestBase


class ToggleStackSleepViewTests(ComposeStackAPITestBase):
    async def acreate_and_deploy_compose_stack(
        self,
        content: str = DOCKER_COMPOSE_MINIMAL,
        slug: str = "my-stack",
    ):
        project = await self.acreate_project(slug="compose")

        create_stack_payload = {
            "slug": slug,
            "user_content": content,
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
            ComposeStack, await ComposeStack.objects.filter(slug=slug).afirst()
        )
        self.assertIsNotNone(stack)

        # Deploy the stack
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
        return project, stack

    async def test_stop_stack_scales_all_services_to_zero(self):
        project, stack = await self.acreate_and_deploy_compose_stack()

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
        project, stack = await self.acreate_and_deploy_compose_stack()

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
