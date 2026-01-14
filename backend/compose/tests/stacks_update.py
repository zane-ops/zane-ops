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
    DOCKER_COMPOSE_WEB_WITH_DB,
    DOCKER_COMPOSE_WEB_ONLY,
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

        initial_computed_content = cast(str, stack.computed_content)

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
        new_computed_content = cast(str, stack.computed_content)
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
x-zane-env:
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

    def test_update_config_content_triggers_version_increment(self):
        """
        When a config's content is modified between deployments,
        the config should be versioned by appending _v{n} to its name.
        This ensures Docker Stack recreates the config.
        """
        initial_content = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes 1;
"""

        project, stack = self.create_and_deploy_compose_stack(
            content=initial_content,
            slug="config-version-stack",
        )

        # Verify initial config was stored
        stack.refresh_from_db()
        initial_configs = cast(dict, stack.configs)
        self.assertIsNotNone(initial_configs.get("nginx_config"))
        nginx_config = initial_configs["nginx_config"]
        self.assertIn("worker_processes 1", nginx_config["content"])
        self.assertEqual(1, nginx_config["version"])

        # Verify initial computed content has config with version 1
        initial_computed_content = cast(str, stack.computed_content)
        self.assertIn("nginx_config_v1:", initial_computed_content)

        # Update config content
        updated_content = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes 4;
"""

        update_payload = {
            "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            "type": ComposeStackChange.ChangeType.UPDATE,
            "new_value": updated_content,
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

        # Deploy the changes
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
        new_configs = cast(dict, stack.configs)
        new_computed_content = cast(str, stack.computed_content)

        print(
            "========= new computed =========",
            new_computed_content,
            "========= end new computed =========",
            sep="\n",
        )

        # Verify config content was updated
        self.assertIsNotNone(new_configs.get("nginx_config"))
        nginx_config = new_configs["nginx_config"]
        self.assertIn("worker_processes 4", nginx_config["content"])
        self.assertEqual(2, nginx_config["version"])

        # Verify computed content has versioned config name (v2 now)
        self.assertIn("nginx_config_v2:", new_computed_content)
        self.assertNotIn("nginx_config_v1:", new_computed_content)

    def test_unchanged_config_content_does_not_increment_version(self):
        """
        When a config's content is unchanged between deployments,
        the config version should not increment.
        """
        initial_content = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes 2;
"""

        project, stack = self.create_and_deploy_compose_stack(
            content=initial_content,
            slug="unchanged-config-stack",
        )

        # Verify initial config
        stack.refresh_from_db()
        initial_configs = cast(dict, stack.configs)

        # Update compose file but keep config content the same
        updated_content = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf
    deploy:
      replicas: 2

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes 2;
"""

        update_payload = {
            "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            "type": ComposeStackChange.ChangeType.UPDATE,
            "new_value": updated_content,
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
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Deploy the changes
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
        new_configs = cast(dict, stack.configs)
        new_computed = cast(str, stack.computed_content)

        # Config content should be identical
        self.assertEqual(
            initial_configs["nginx_config"]["content"],
            new_configs["nginx_config"]["content"],
        )
        # Version should remain 1 since content didn't change
        self.assertEqual(1, new_configs["nginx_config"]["version"])

        # Config name should still be at v1 since content didn't change
        self.assertIn("nginx_config_v1:", new_computed)
        self.assertNotIn("nginx_config_v2:", new_computed)

    def test_multiple_config_updates_increment_versions_independently(self):
        """
        When multiple configs exist and only some change,
        only the changed configs should get version increments.
        """
        initial_content = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf
      - source: app_config
        target: /etc/nginx/conf.d/app.conf

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes 1;
  app_config:
    content: |
      server {
        listen 80;
      }
"""

        project, stack = self.create_and_deploy_compose_stack(
            content=initial_content,
            slug="multi-config-stack",
        )

        # Update only nginx_config
        updated_content = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf
      - source: app_config
        target: /etc/nginx/conf.d/app.conf

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes 4;
  app_config:
    content: |
      server {
        listen 80;
      }
"""

        update_payload = {
            "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            "type": ComposeStackChange.ChangeType.UPDATE,
            "new_value": updated_content,
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

        stack.refresh_from_db()
        new_computed = cast(str, stack.computed_content)

        print(
            "========= multi-config computed =========",
            new_computed,
            "========= end multi-config computed =========",
            sep="\n",
        )

        # nginx_config should be at v2 (changed)
        self.assertIn("nginx_config_v2:", new_computed)
        # app_config should still be at v1 (didn't change)
        self.assertIn("app_config_v1:", new_computed)
        self.assertNotIn("app_config_v2:", new_computed)

    @responses.activate()
    async def test_update_compose_removes_unreferenced_services(self):
        """
        When updating a compose stack to remove services,
        the removed services should be deleted from Docker Swarm
        and no longer appear in the stack's computed content.

        Use case: A stack with web, db, and cache services is updated
        to only have the web service. The db and cache services should
        be removed from Docker Swarm.
        """
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_WITH_DB,
            slug="service-removal-stack",
        )

        # Verify initial services exist in computed content
        await stack.arefresh_from_db()

        # Verify initial services exist in Docker
        initial_web_service = self.fake_docker_client.services_get(
            f"{stack.name}_{stack.hash_prefix}_web"
        )
        self.assertIsNotNone(initial_web_service)

        initial_db_service = self.fake_docker_client.services_get(
            f"{stack.name}_{stack.hash_prefix}_db"
        )
        self.assertIsNotNone(initial_db_service)

        initial_cache_service = self.fake_docker_client.services_get(
            f"{stack.name}_{stack.hash_prefix}_cache"
        )
        self.assertIsNotNone(initial_cache_service)

        # Update to only have web service (remove db and cache)
        update_payload = {
            "field": ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            "type": ComposeStackChange.ChangeType.UPDATE,
            "new_value": DOCKER_COMPOSE_WEB_ONLY,
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
        new_computed = cast(str, stack.computed_content)

        print(
            "========= new computed =========",
            new_computed,
            "========= end new computed =========",
            sep="\n",
        )

        # Verify web service still exists in Docker
        web_service = self.fake_docker_client.services_get(
            f"{stack.name}_{stack.hash_prefix}_web"
        )
        self.assertIsNotNone(web_service)

        # Verify db and cache services are removed from Docker
        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]}
        )
        self.assertEqual(1, len(service_list))
        self.assertEqual(
            f"{stack.name}_{stack.hash_prefix}_web",
            service_list[0].name,
        )
