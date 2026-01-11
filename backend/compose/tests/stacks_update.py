from django.urls import reverse
from rest_framework import status
import responses
import requests
from django.conf import settings

from zane_api.models import Environment
from ..models import ComposeStack, ComposeStackChange, ComposeStackEnvOverride
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WEB_SERVICE,
)
from typing import cast
from zane_api.utils import jprint
from temporal.helpers import ZaneProxyClient

from .stacks import ComposeStackAPITestBase
from ..dtos import ComposeStackUrlRouteDto


class ComposeStackRequestUpdateViewTests(ComposeStackAPITestBase):
    async def acreate_and_deploy_compose_stack(
        self,
        content: str,
        slug="my-stack",
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
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await stack.arefresh_from_db()
        print(
            "========= original =========",
            stack.user_content,
            "========= end original =========",
            sep="\n",
        )
        print(
            "========= computed =========",
            stack.computed_content,
            "========= end computed =========",
            sep="\n",
        )

        return project, stack

    def create_and_deploy_compose_stack(
        self,
        content: str,
        slug="my-stack",
    ):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": slug,
            "user_content": content,
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

        stack = cast(ComposeStack, ComposeStack.objects.filter(slug=slug).first())
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.user_content)
        self.assertIsNone(stack.computed_content)

        # Deploy the stack
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        stack.refresh_from_db()
        print(
            "========= original =========",
            stack.user_content,
            "========= end original =========",
            sep="\n",
        )
        print(
            "========= computed =========",
            stack.computed_content,
            "========= end computed =========",
            sep="\n",
        )

        return project, stack

    def test_update_content_request_create_change(self):
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL, slug="minimal"
        )

        # Request content update with new compose file
        update_payload = {
            "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            "type": "UPDATE",
            "new_value": DOCKER_COMPOSE_SIMPLE_DB,
        }

        response = self.client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data=update_payload,
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify a change was created
        stack.refresh_from_db()
        content_change = stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            type=ComposeStackChange.ChangeType.UPDATE,
        ).first()
        self.assertIsNotNone(content_change)
        content_change = cast(ComposeStackChange, content_change)
        self.assertFalse(content_change.applied)

        # Verify new_value contains the updated content
        new_value = cast(dict, content_change.new_value)
        self.assertEqual(DOCKER_COMPOSE_SIMPLE_DB.strip(), new_value)

    def test_update_env_overrides_create_change(self):
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL, slug="env-override-stack"
        )

        # Request env override ADD change
        add_payload = {
            "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
            "type": ComposeStackChange.ChangeType.ADD,
            "new_value": {"key": "MY_VAR", "value": "my_value"},
        }

        response = self.client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data=add_payload,
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify a change was created
        stack.refresh_from_db()
        env_change = stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        ).first()
        self.assertIsNotNone(env_change)
        env_change = cast(ComposeStackChange, env_change)
        self.assertFalse(env_change.applied)

        # Verify new_value contains the env key/value
        new_value = cast(dict, env_change.new_value)
        self.assertEqual("MY_VAR", new_value.get("key"))
        self.assertEqual("my_value", new_value.get("value"))

    def test_update_env_do_not_invalidate_compose_content(self):
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
            slug="url-env-stack",
        )

        # Request env override ADD change
        add_payload = {
            "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
            "type": ComposeStackChange.ChangeType.ADD,
            "new_value": {
                "key": "API_PORT",
                # API port env is passed to the `zane.http.routes.{n}.port`
                # which should be a valid integer
                "value": "invalid_int",
            },
        }

        response = self.client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data=add_payload,
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "new_value.value"))

    def test_remove_env_regenerate_env_placeholders(self):
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_PLACEHOLDERS,
            slug="placeholder-stack",
        )

        env = cast(
            ComposeStackEnvOverride,
            stack.env_overrides.filter(key="POSTGRES_USER").first(),
        )
        self.assertIsNotNone(env)

        # delete placeholder env
        payload = {
            "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
            "type": ComposeStackChange.ChangeType.DELETE,
            "item_id": env.id,
        }

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
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # redeploy the stack
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        stack.refresh_from_db()
        print(
            "========= new computed =========",
            stack.computed_content,
            "========= end new computed =========",
            sep="\n",
        )

        # The env override should be re-created
        env = cast(
            ComposeStackEnvOverride,
            stack.env_overrides.filter(key="POSTGRES_USER").first(),
        )
        self.assertIsNotNone(env)

    def test_update_env_overrides_recompute_content_on_deploy(self):
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
            slug="placeholder-stack",
        )

        initial_computed_content = stack.computed_content

        # add new env
        payload = {
            "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
            "type": ComposeStackChange.ChangeType.ADD,
            "new_value": {
                "key": "APP_DOMAIN",
                "value": "op.zaneops.dev",
            },
        }

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
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # redeploy the stack
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        stack.refresh_from_db()
        new_computed_content = stack.computed_content
        print(
            "========= new computed =========",
            new_computed_content,
            "========= end new computed =========",
            sep="\n",
        )

        # The env override should be created
        env = cast(
            ComposeStackEnvOverride,
            stack.env_overrides.filter(key="APP_DOMAIN").first(),
        )
        self.assertIsNotNone(env)
        self.assertEqual(env.value, "op.zaneops.dev")
        self.assertEqual(env.key, "APP_DOMAIN")

        self.assertNotEqual(initial_computed_content, new_computed_content)
        urls = cast(dict[str, list[dict]], stack.urls)
        self.assertIsNotNone(cast(dict, stack.urls).get("dashboard"))

        dashboard_route = ComposeStackUrlRouteDto.from_dict(urls["dashboard"][0])
        self.assertEqual("dashboard.op.zaneops.dev", dashboard_route.domain)

        api_route = ComposeStackUrlRouteDto.from_dict(urls["api"][0])
        self.assertEqual("api.op.zaneops.dev", api_route.domain)

    @responses.activate()
    async def test_update_compose_with_urls_cleanup_old_unused_urls(self):
        """
        When updating a compose stack's content to change URLs,
        the old URLs should be removed from the proxy and replaced with new ones.
        """
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE,
            slug="url-cleanup-stack",
        )

        # Verify initial URLs exist
        initial_urls = cast(dict, stack.urls)
        self.assertIn("web", initial_urls)
        initial_web_route = ComposeStackUrlRouteDto.from_dict(initial_urls["web"][0])
        self.assertEqual("hello.127-0-0-1.sslip.io", initial_web_route.domain)

        # Verify old route is registered in proxy
        web_proxy_response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=initial_web_route,
            )
        )
        self.assertEqual(200, web_proxy_response.status_code)

        # Update content to have completely different services/URLs
        new_content = """
x-env:
  NEW_DOMAIN: "newservice.example.com"

services:
  newservice:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "80"
        zane.http.routes.0.domain: "${NEW_DOMAIN}"
        zane.http.routes.0.base_path: "/"
"""

        update_payload = {
            "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            "type": ComposeStackChange.ChangeType.UPDATE,
            "new_value": new_content,
        }

        response = await self.async_client.put(
            reverse(
                "compose:stacks.request_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data=update_payload,
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the changes
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await stack.arefresh_from_db()
        new_urls = cast(dict, stack.urls)

        # Old services/URLs should be removed from stack
        self.assertNotIn("web", new_urls)

        # New service/URL should exist
        self.assertIn("newservice", new_urls)
        new_route = ComposeStackUrlRouteDto.from_dict(new_urls["newservice"][0])
        self.assertEqual("newservice.example.com", new_route.domain)

        # Verify old route is removed from proxy (404)
        web_proxy_response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=initial_web_route,
            )
        )
        self.assertEqual(404, web_proxy_response.status_code)

        # Verify new route is registered in proxy
        new_proxy_response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="newservice",
                url=new_route,
            )
        )
        self.assertEqual(200, new_proxy_response.status_code)
