from django.urls import reverse
import os
import responses
from rest_framework import status
from unittest.mock import patch

from zane_api.models import Project, Environment
from zane_api.tests.base import AuthAPITestCase, FakeDockerClient
from ..models import ComposeStack, ComposeStackChange, ComposeStackDeployment
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WITH_HOST_VOLUME,
    DOCKER_COMPOSE_EXTERNAL_VOLUME,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_MULTIPLE_ROUTES,
    DOCKER_COMPOSE_WITH_DEPENDS_ON,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WITH_EXTERNAL_CONFIGS,
    DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
    DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES,
    DOCKER_COMPOSE_WITH_X_ENV_IN_CONFIGS,
    DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
    INVALID_COMPOSE_NO_IMAGE,
    INVALID_COMPOSE_RELATIVE_BIND_VOLUME,
    INVALID_COMPOSE_SERVICE_NAME_SPECIAL,
    INVALID_COMPOSE_YAML_SYNTAX,
    INVALID_COMPOSE_EMPTY,
    INVALID_COMPOSE_NO_SERVICES,
    INVALID_COMPOSE_EMPTY_SERVICES,
    INVALID_COMPOSE_SERVICES_NOT_DICT,
    INVALID_COMPOSE_WITH_CONFIG_FILE_LOCATION,
    INVALID_COMPOSE_ROUTE_MISSING_PORT,
    INVALID_COMPOSE_ROUTE_MISSING_DOMAIN,
    INVALID_COMPOSE_ROUTE_INVALID_PORT_ZERO,
    INVALID_COMPOSE_ROUTE_INVALID_PORT_NEGATIVE,
    INVALID_COMPOSE_X_ENV_NOT_DICT,
)
from typing import Any, cast
from zane_api.utils import jprint, find_item_in_sequence
from ..dtos import ComposeStackServiceStatus
import requests
from temporal.helpers import ZaneProxyClient
from django.conf import settings
from temporal.schedules import MonitorComposeStackWorkflow
from temporal.activities import ComposeStackActivities
from compose.dtos import ComposeStackSnapshot
from temporalio import activity
from temporal.shared import ComposeStackBuildDetails
from compose.dtos import ComposeStackUrlRouteDto


class ComposeStackAPITestBase(AuthAPITestCase):
    def create_project(self, slug="my-project"):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": slug},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )
        return Project.objects.get(slug=slug)

    async def acreate_project(self, slug="my-project"):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": slug},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )
        return await Project.objects.aget(slug=slug)


class CreateComposeStackViewTests(ComposeStackAPITestBase):
    def test_create_simple_compose_stack(self):
        project = self.create_project()

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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="my-stack").first()
        )
        self.assertIsNotNone(created_stack)
        self.assertIsNone(created_stack.user_content)
        self.assertIsNone(created_stack.computed_content)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)
        self.assertEqual(
            new_value.get("user_content"),
            DOCKER_COMPOSE_MINIMAL.strip(),
        )
        self.assertIsNotNone(new_value.get("computed_content"))
        self.assertNotEqual(
            new_value.get("computed_content"),
            DOCKER_COMPOSE_MINIMAL.strip(),
        )
        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

    def test_create_compose_stack_with_volumes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "db-stack",
            "user_content": DOCKER_COMPOSE_SIMPLE_DB,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="db-stack").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        self.assertIn("volumes", computed_dict)
        _, initial_volume = next(iter(computed_dict["volumes"].items()))
        self.assertIsNotNone(initial_volume.get("labels"))
        self.assertIn("zane-managed", initial_volume.get("labels"))
        self.assertIn("zane-stack", initial_volume.get("labels"))
        self.assertIn("zane-project", initial_volume.get("labels"))

        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        service_name, service_config = next(iter(services.items()))
        self.assertNotEqual("postgres", service_name)
        self.assertTrue(service_name.endswith("postgres"))

        db_service = cast(dict, service_config)

        self.assertIn("volumes", db_service)
        service_volumes: list[dict[str, Any]] = cast(list, db_service.get("volumes"))
        self.assertGreater(len(service_volumes), 0, "Service should have volume mounts")
        db_volume = find_item_in_sequence(
            lambda v: v["type"] == "volume", service_volumes
        )
        db_volume = cast(dict[str, Any], db_volume)
        self.assertIsNotNone(db_volume)
        self.assertIsInstance(db_volume, dict)
        self.assertIsNotNone(db_volume.get("source"))

        self.assertEqual("db-data", db_volume["source"])
        self.assertEqual("/var/lib/postgresql", db_volume["target"])

    def test_create_compose_stack_with_host_volumes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "portainer",
            "user_content": DOCKER_COMPOSE_WITH_HOST_VOLUME,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="portainer").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        self.assertNotIn("volumes", computed_dict)

        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        _, service_config = next(iter(services.items()))
        portainer_service = cast(dict, service_config)

        self.assertIn("volumes", portainer_service)
        service_volumes: list[dict[str, Any]] = cast(
            list, portainer_service.get("volumes")
        )
        self.assertGreater(len(service_volumes), 0, "Service should have volume mounts")
        db_volume = find_item_in_sequence(
            lambda v: v["type"] == "bind", service_volumes
        )
        db_volume = cast(dict[str, Any], db_volume)
        self.assertIsNotNone(db_volume)
        self.assertIsInstance(db_volume, dict)
        self.assertIsNotNone(db_volume.get("source"))

        self.assertEqual("/var/run/docker.sock", db_volume["source"])
        self.assertEqual("/var/run/docker.sock", db_volume["target"])
        self.assertTrue(db_volume.get("read_only"))

    def test_create_compose_stack_with_external_volume_do_not_add_labels_and_prefix(
        self,
    ):
        project = self.create_project()

        create_stack_payload = {
            "slug": "myapp",
            "user_content": DOCKER_COMPOSE_EXTERNAL_VOLUME,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="myapp").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        self.assertIn("volumes", computed_dict)

        name, initial_volume = next(iter(computed_dict["volumes"].items()))
        self.assertIsNone(initial_volume.get("labels"))
        self.assertEqual("shared_data", name)
        self.assertEqual({"external": True}, initial_volume)

        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        _, service_config = next(iter(services.items()))
        app_service = cast(dict, service_config)

        self.assertIn("volumes", app_service)
        service_volumes: list[dict[str, Any]] = cast(list, app_service.get("volumes"))
        volume = find_item_in_sequence(lambda v: v["type"] == "volume", service_volumes)
        volume = cast(dict[str, Any], volume)
        self.assertIsNotNone(volume)
        self.assertEqual("shared_data", volume["source"])

    def test_create_compose_stack_with_url(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx",
            "user_content": DOCKER_COMPOSE_WEB_SERVICE,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="nginx").first()
        )
        self.assertIsNotNone(created_stack)

        computed_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(computed_change)
        self.assertIsNotNone(computed_change.new_value)
        new_value = cast(dict, computed_change.new_value)

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        print(
            "========= original =========",
            cast(dict, new_value).get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            cast(dict, new_value).get("computed_content"),
            sep="\n",
        )

        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        _, service_config = next(iter(services.items()))
        web_service = cast(dict, service_config)

        self.assertIn("deploy", web_service)
        deploy_config = cast(dict, web_service.get("deploy"))
        self.assertIn("labels", deploy_config)

        labels = cast(dict, deploy_config.get("labels"))

        self.assertIn("zane.http.port", labels)
        self.assertEqual("80", labels["zane.http.port"])

        self.assertIn("zane.http.routes.0.domain", labels)
        self.assertEqual(
            "hello.127-0-0-1.sslip.io", labels["zane.http.routes.0.domain"]
        )

        self.assertIn("zane.http.routes.0.base_path", labels)
        self.assertEqual("/", labels["zane.http.routes.0.base_path"])

        extracted_urls = cast(dict, new_value.get("urls"))
        self.assertIsNotNone(extracted_urls)
        self.assertEqual(len(extracted_urls), 1)

        routes = cast(list, extracted_urls["web"])
        self.assertEqual(len(routes), 1)

        route = cast(dict, routes[0])
        self.assertEqual(route["domain"], "hello.127-0-0-1.sslip.io")
        self.assertEqual(route["base_path"], "/")
        self.assertEqual(route["port"], 80)
        self.assertTrue(route["strip_prefix"])

    def test_create_compose_stack_with_multiple_urls(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "api-stack",
            "user_content": DOCKER_COMPOSE_MULTIPLE_ROUTES,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="api-stack").first()
        )
        self.assertIsNotNone(created_stack)

        computed_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(computed_change)
        self.assertIsNotNone(computed_change.new_value)
        new_value = cast(dict, computed_change.new_value)

        extracted_urls = cast(dict, new_value.get("urls"))
        self.assertIsNotNone(extracted_urls)
        self.assertEqual(len(extracted_urls), 1)

        routes = cast(list, extracted_urls["api"])
        self.assertEqual(len(routes), 2)

        route_0 = cast(dict, routes[0])
        self.assertEqual(route_0["domain"], "api.example.com")
        self.assertEqual(route_0["base_path"], "/")
        self.assertEqual(route_0["port"], 3000)
        self.assertFalse(route_0["strip_prefix"])

        route_1 = cast(dict, routes[1])
        self.assertEqual(route_1["domain"], "example.com")
        self.assertEqual(route_1["base_path"], "/api")
        self.assertEqual(route_1["port"], 3001)
        self.assertTrue(route_1["strip_prefix"])

    def test_create_compose_stack_with_dependencies(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "django-app",
            "user_content": DOCKER_COMPOSE_WITH_DEPENDS_ON,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="django-app").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)
        self.assertEqual(len(services), 3, "Should have 3 services: web, db, cache")
        web_service_name = None
        db_service_name = None
        cache_service_name = None

        for service_name in services.keys():
            if service_name.endswith("_web"):
                web_service_name = service_name
            elif service_name.endswith("_db"):
                db_service_name = service_name
            elif service_name.endswith("_cache"):
                cache_service_name = service_name

        self.assertIsNotNone(web_service_name, "Web service should exist")
        self.assertIsNotNone(db_service_name, "DB service should exist")
        self.assertIsNotNone(cache_service_name, "Cache service should exist")

        web_service = cast(dict, services[web_service_name])

        self.assertIn("depends_on", web_service, "Web service should have depends_on")
        depends_on = cast(list[str], web_service.get("depends_on"))
        self.assertEqual(len(depends_on), 2, "Web service should depend on 2 services")
        db_dependency = find_item_in_sequence(lambda d: d.endswith("_db"), depends_on)
        cache_dependency = find_item_in_sequence(
            lambda d: d.endswith("_cache"), depends_on
        )
        self.assertIsNotNone(db_dependency)
        self.assertIsNotNone(cache_dependency)

    def test_create_compose_with_env_placeholders(self):
        """
        Test that x-env placeholders are resolved and substituted into service environments.
        Placeholders like {{ generate_username }} are only supported in x-env section.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "placeholder-stack",
            "user_content": DOCKER_COMPOSE_WITH_PLACEHOLDERS,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="placeholder-stack").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        services = cast(dict, computed_dict.get("services"))

        # Find db service and verify env vars are resolved
        db_service = None
        for service_name, service_config in services.items():
            if service_name.endswith("_db"):
                db_service = service_config
                break

        self.assertIsNotNone(db_service)
        db_service = cast(dict, db_service)
        self.assertIn("environment", db_service)
        env = cast(dict, db_service.get("environment"))

        self.assertIn("POSTGRES_USER", env)
        self.assertIn("POSTGRES_PASSWORD", env)
        self.assertIn("POSTGRES_DB", env)

        # Verify placeholders were resolved (not template strings or ${} refs)
        self.assertNotEqual("{{ generate_username }}", env["POSTGRES_USER"])
        self.assertNotEqual("${POSTGRES_USER}", env["POSTGRES_USER"])
        self.assertNotEqual("{{ generate_secure_password }}", env["POSTGRES_PASSWORD"])
        self.assertNotEqual("${POSTGRES_PASSWORD}", env["POSTGRES_PASSWORD"])
        self.assertNotEqual("{{ generate_random_slug }}", env["POSTGRES_DB"])
        self.assertNotEqual("${POSTGRES_DB}", env["POSTGRES_DB"])

        # Find app service and verify env vars are resolved
        app_service = None
        for service_name, service_config in services.items():
            if service_name.endswith("_app"):
                app_service = service_config
                break

        self.assertIsNotNone(app_service)
        app_service = cast(dict, app_service)
        self.assertIn("environment", app_service)
        app_env = cast(dict, app_service.get("environment"))

        self.assertIn("API_TOKEN", app_env)
        self.assertIn("SECRET_KEY", app_env)
        self.assertNotEqual("{{ generate_random_chars_32 }}", app_env["API_TOKEN"])
        self.assertNotEqual("${API_TOKEN}", app_env["API_TOKEN"])
        self.assertNotEqual("{{ generate_random_chars_64 }}", app_env["SECRET_KEY"])
        self.assertNotEqual("${SECRET_KEY}", app_env["SECRET_KEY"])

        # Verify env override changes were created for all x-env variables
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )
        self.assertEqual(5, env_changes.count(), "Should have 5 env override changes")

        # Verify each x-env variable has a corresponding env override change
        env_change_keys = {
            cast(dict, change.new_value).get("key") for change in env_changes
        }
        expected_keys = {
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "API_TOKEN",
            "SECRET_KEY",
        }
        self.assertEqual(expected_keys, env_change_keys)

        # Verify all values are resolved (no templates or refs)
        for change in env_changes:
            change_value = cast(dict, change.new_value)
            value = cast(str, change_value.get("value"))
            self.assertIsNotNone(value)
            self.assertGreater(len(value), 0)
            self.assertNotEqual("{{ generate_username }}", value)
            self.assertNotEqual("{{ generate_secure_password }}", value)
            self.assertNotEqual("{{ generate_random_slug }}", value)
            self.assertNotEqual("{{ generate_random_chars_32 }}", value)
            self.assertNotEqual("{{ generate_random_chars_64 }}", value)

    def test_create_compose_stack_with_external_configs(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx-external-configs",
            "user_content": DOCKER_COMPOSE_WITH_EXTERNAL_CONFIGS,
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

        created_stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="nginx-external-configs").first(),
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        self.assertIn("configs", computed_dict)
        configs = cast(dict, computed_dict["configs"])

        self.assertIn("nginx_config", configs)
        self.assertIn("site_config", configs)
        self.assertEqual({"external": True}, configs["nginx_config"])
        self.assertEqual({"external": True}, configs["site_config"])

        services = cast(dict, computed_dict.get("services"))
        _, service_config = next(iter(services.items()))
        web_service = cast(dict, service_config)

        self.assertIn("configs", web_service)
        service_configs = cast(list, web_service.get("configs"))
        self.assertEqual(len(service_configs), 2)
        nginx_config = find_item_in_sequence(
            lambda c: c["source"] == "nginx_config", service_configs
        )
        site_config = find_item_in_sequence(
            lambda c: c["source"] == "site_config", service_configs
        )

        self.assertIsNotNone(nginx_config)
        self.assertIsNotNone(site_config)
        self.assertEqual(
            "/etc/nginx/nginx.conf", cast(dict, nginx_config).get("target")
        )
        self.assertEqual(
            "/etc/nginx/conf.d/default.conf", cast(dict, site_config).get("target")
        )

    def test_create_compose_stack_with_inline_configs(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx-inline-configs",
            "user_content": DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
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

        created_stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="nginx-inline-configs").first(),
        )
        self.assertIsNotNone(created_stack)

        computed_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(computed_change)
        self.assertIsNotNone(computed_change.new_value)
        new_value = cast(dict, computed_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        self.assertIsNotNone(computed_dict)

        self.assertIn("configs", computed_dict)
        configs = cast(dict, computed_dict["configs"])
        self.assertIn("nginx_config", configs)

        nginx_config = cast(dict, configs["nginx_config"])
        self.assertIsNotNone(nginx_config.get("file"))
        self.assertIsNone(nginx_config.get("content"))

        nginx_config_labels = nginx_config.get("labels")
        self.assertIsNotNone(nginx_config_labels)
        nginx_config_labels = cast(dict, nginx_config_labels)
        self.assertIn("zane-managed", nginx_config_labels)
        self.assertIn("zane-stack", nginx_config_labels)
        self.assertIn("zane-project", nginx_config_labels)

        configs_data = cast(dict, new_value.get("configs"))
        self.assertIsNotNone(configs_data)
        self.assertIn("nginx_config", configs_data)

        expected_content = (
            "user nginx;\n"
            "worker_processes auto;\n"
            "events {\n"
            "  worker_connections 1024;\n"
            "}"
        )
        self.assertEqual(expected_content, configs_data["nginx_config"])

        services = cast(dict, computed_dict.get("services"))
        _, service_config = next(iter(services.items()))
        web_service = cast(dict, service_config)

        self.assertIn("configs", web_service)
        service_configs = cast(list, web_service.get("configs"))
        self.assertEqual(len(service_configs), 1)

        nginx_config_mount = find_item_in_sequence(
            lambda c: c["source"] == "nginx_config", service_configs
        )
        self.assertIsNotNone(nginx_config_mount)
        self.assertEqual(
            "/etc/nginx/nginx.conf", cast(dict, nginx_config_mount).get("target")
        )

    def test_create_compose_stack_without_image_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "no-image-stack",
            "user_content": INVALID_COMPOSE_NO_IMAGE,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_relative_bind_volume_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "relative-bind-volume",
            "user_content": INVALID_COMPOSE_RELATIVE_BIND_VOLUME,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_invalid_yaml_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "invalid-yaml",
            "user_content": INVALID_COMPOSE_YAML_SYNTAX,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_special_char_service_name_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "special-char-service",
            "user_content": INVALID_COMPOSE_SERVICE_NAME_SPECIAL,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_empty_content_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "empty-compose",
            "user_content": INVALID_COMPOSE_EMPTY,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_no_services_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "no-services",
            "user_content": INVALID_COMPOSE_NO_SERVICES,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_empty_service_list_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "no-services",
            "user_content": INVALID_COMPOSE_EMPTY_SERVICES,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_services_as_list_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "services-list",
            "user_content": INVALID_COMPOSE_SERVICES_NOT_DICT,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_config_file_path_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "relative-config-path",
            "user_content": INVALID_COMPOSE_WITH_CONFIG_FILE_LOCATION,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_route_missing_port_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "missing-port",
            "user_content": INVALID_COMPOSE_ROUTE_MISSING_PORT,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_route_missing_domain_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "missing-domain",
            "user_content": INVALID_COMPOSE_ROUTE_MISSING_DOMAIN,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_route_port_zero_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "port-zero",
            "user_content": INVALID_COMPOSE_ROUTE_INVALID_PORT_ZERO,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_route_port_negative_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "port-negative",
            "user_content": INVALID_COMPOSE_ROUTE_INVALID_PORT_NEGATIVE,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_stack_with_network_aliases(self):
        project = self.create_project()

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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="my-stack").first()
        )
        self.assertIsNotNone(created_stack)
        self.assertEqual("zn-my-stack", created_stack.network_alias_prefix)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        services = cast(dict, computed_dict.get("services"))

        # Find the redis service
        _, redis_service = next(iter(services.items()))

        # Check networks configuration
        self.assertIn("networks", redis_service)
        networks = cast(dict, redis_service.get("networks"))

        # Should have zane network (no aliases)
        self.assertIn("zane", networks)
        self.assertIsNone(networks["zane"])

        # Should have default network with alias to original service name
        self.assertIn("default", networks)
        default_network = cast(dict, networks.get("default"))
        self.assertIsNotNone(default_network)
        self.assertIn("aliases", default_network)
        default_aliases = cast(list, default_network.get("aliases"))
        self.assertIn("redis", default_aliases)

        # Should have environment network with alias using network_alias_prefix
        env_network_name = None
        for network_name in networks.keys():
            if network_name.startswith("net-prj_"):
                env_network_name = network_name
                break

        self.assertIsNotNone(env_network_name)
        env_network = cast(dict, networks.get(env_network_name))
        self.assertIsNotNone(env_network)
        self.assertIn("aliases", env_network)
        env_aliases = cast(list, env_network.get("aliases"))
        self.assertIn("zn-my-stack-redis", env_aliases)

    def test_create_compose_with_x_env_overrides(self):
        """
        Test that x-env section in compose file:
        1. Extracts env variables with placeholders and resolves them
        2. Resolves computed variables that reference other variables (e.g., ${MAIN_DOMAIN})
        3. Substitutes resolved values into service environment variables
        4. Creates env override changes for all resolved variables
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "x-env-stack",
            "user_content": DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="x-env-stack").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_spec"))
        services = cast(dict, computed_dict.get("services"))

        # Find db service and verify env vars are resolved
        db_service = None
        for service_name, service_config in services.items():
            if service_name.endswith("_db"):
                db_service = service_config
                break

        self.assertIsNotNone(db_service)
        db_service = cast(dict, db_service)
        self.assertIn("environment", db_service)
        db_env = cast(dict, db_service.get("environment"))

        # Verify static values are substituted
        self.assertEqual("openpanel", db_env["POSTGRES_USER"])
        self.assertEqual("openpanel-db", db_env["POSTGRES_DB"])
        # Verify placeholder was resolved (not the template string)
        self.assertNotEqual(
            "{{ generate_secure_password }}", db_env["POSTGRES_PASSWORD"]
        )

        # Find api service and verify computed env vars are resolved
        api_service = None
        for service_name, service_config in services.items():
            if service_name.endswith("_api"):
                api_service = service_config
                break

        self.assertIsNotNone(api_service)
        api_service = cast(dict, api_service)
        self.assertIn("environment", api_service)
        api_env = cast(dict, api_service.get("environment"))

        # Verify computed variables are resolved (chained resolution)
        # SERVICE_FQDN_OPDASHBOARD should resolve to "http://openpanel.127-0-0-1.sslip.io"
        self.assertEqual(
            "http://openpanel.127-0-0-1.sslip.io", api_env["DASHBOARD_URL"]
        )
        self.assertEqual("http://api.openpanel.127-0-0-1.sslip.io", api_env["API_URL"])

        # DATABASE_URL should have all variables resolved
        # Should be like: postgres://openpanel:<generated_password>@db:5432/openpanel-db
        self.assertIn("postgres://openpanel:", api_env["DATABASE_URL"])
        self.assertIn("@db:5432/openpanel-db", api_env["DATABASE_URL"])
        self.assertNotIn("${", api_env["DATABASE_URL"])  # No unresolved variables

        # Verify env override changes were created only for generated variables
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )
        # Should have exactly 2 env override changes (for generated variables only)
        self.assertEqual(2, env_changes.count())

        env_change_keys = {
            cast(dict, change.new_value).get("key") for change in env_changes
        }
        expected_keys = {
            "SERVICE_PASSWORD_POSTGRES",
            "SERVICE_PASSWORD_REDIS",
        }
        self.assertEqual(expected_keys, env_change_keys)

        # Verify generated values are not templates
        for change in env_changes:
            change_value = cast(dict, change.new_value)
            value = cast(str, change_value.get("value"))
            self.assertNotEqual("{{ generate_secure_password }}", value)
            self.assertIsNotNone(value)
            self.assertGreater(len(value), 0)

        # Verify x-env values in computed_content change
        x_env = computed_dict.get("x-env", {})

        # Static values
        self.assertEqual("openpanel", x_env["SERVICE_USER_POSTGRES"])
        self.assertEqual("openpanel-db", x_env["OPENPANEL_POSTGRES_DB"])
        self.assertEqual("openpanel.127-0-0-1.sslip.io", x_env["MAIN_DOMAIN"])
        self.assertEqual("api.openpanel.127-0-0-1.sslip.io", x_env["API_DOMAIN"])

        # Computed values (chained resolution)
        self.assertEqual(
            "http://openpanel.127-0-0-1.sslip.io", x_env["SERVICE_FQDN_OPDASHBOARD"]
        )
        self.assertEqual(
            "http://api.openpanel.127-0-0-1.sslip.io", x_env["SERVICE_FQDN_OPAPI"]
        )

        # Generated values
        self.assertNotEqual(
            "{{ generate_secure_password }}", x_env["SERVICE_PASSWORD_POSTGRES"]
        )
        self.assertNotEqual(
            "{{ generate_secure_password }}", x_env["SERVICE_PASSWORD_REDIS"]
        )

        # DATABASE_URL should be fully resolved
        self.assertIn("postgres://openpanel:", x_env["DATABASE_URL"])
        self.assertIn("@db:5432/openpanel-db", x_env["DATABASE_URL"])
        self.assertNotIn("${", x_env["DATABASE_URL"])

    def test_create_compose_with_x_env_not_dict_fails(self):
        """Test that x-env must be a dictionary, not a list."""
        project = self.create_project()

        create_stack_payload = {
            "slug": "x-env-invalid",
            "user_content": INVALID_COMPOSE_X_ENV_NOT_DICT,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user_content"))

    def test_create_compose_with_x_env_in_config_content(self):
        """
        Test that x-env variables are resolved in inline config content.
        Variables like ${APP_PORT} in config file content should be substituted.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "x-env-config-stack",
            "user_content": DOCKER_COMPOSE_WITH_X_ENV_IN_CONFIGS,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="x-env-config-stack").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_content"),
            sep="\n",
        )

        # Get the resolved config content
        configs_data = cast(dict, new_value.get("configs"))
        self.assertIsNotNone(configs_data)
        self.assertIn("app_config", configs_data)

        config_content = configs_data["app_config"]

        # Verify static values are substituted in config content
        self.assertIn("listen 8080;", config_content)
        self.assertIn("server_name app.example.com;", config_content)
        self.assertIn("proxy_pass http://app.example.com:8080;", config_content)
        self.assertIn('X-App-Name "myapp"', config_content)

        # Verify generated password is substituted (not the template)
        self.assertNotIn("{{ generate_secure_password }}", config_content)
        self.assertNotIn("${APP_SECRET}", config_content)
        self.assertIn("X-App-Secret", config_content)

        # Verify no unresolved ${} placeholders remain
        self.assertNotIn("${APP_PORT}", config_content)
        self.assertNotIn("${APP_HOST}", config_content)
        self.assertNotIn("${APP_URL}", config_content)
        self.assertNotIn("${APP_NAME}", config_content)

    def test_create_compose_with_x_env_in_urls(self):
        """
        Test that x-env variables are resolved in URL routing labels.
        Variables like ${API_DOMAIN} in deploy labels should be substituted.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "x-env-urls-stack",
            "user_content": DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
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

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="x-env-urls-stack").first()
        )
        self.assertIsNotNone(created_stack)

        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        # Get the resolved URLs
        urls_data = cast(dict, new_value.get("urls"))
        self.assertIsNotNone(urls_data)

        # Verify api service URL is resolved
        self.assertIn("api", urls_data)
        api_routes = urls_data["api"]
        self.assertEqual(1, len(api_routes))
        self.assertEqual("api.myapp.com", api_routes[0]["domain"])
        self.assertEqual(3000, api_routes[0]["port"])

        # Verify dashboard service URL is resolved
        self.assertIn("dashboard", urls_data)
        dashboard_routes = urls_data["dashboard"]
        self.assertEqual(1, len(dashboard_routes))
        self.assertEqual("dashboard.myapp.com", dashboard_routes[0]["domain"])
        self.assertEqual(8080, dashboard_routes[0]["port"])


class DeployComposeStackViewTests(ComposeStackAPITestBase):
    def test_deploy_simple_compose_apply_changes(self):
        project = self.create_project()

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

        stack = cast(ComposeStack, ComposeStack.objects.filter(slug="my-stack").first())
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.user_content)
        self.assertIsNone(stack.computed_content)

        # Deploy the stack
        response = self.client.post(
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
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify deployment created with snapshot
        deployment = ComposeStackDeployment.objects.filter(stack=stack).first()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)
        self.assertIsNotNone(deployment.stack_snapshot)
        snapshot = cast(dict, deployment.stack_snapshot)
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), snapshot.get("user_content"))
        self.assertIsNotNone(snapshot.get("computed_content"))

        # Verify changes are applied
        stack.refresh_from_db()
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), stack.user_content)
        self.assertIsNotNone(stack.computed_content)
        self.assertNotEqual(stack.user_content, stack.computed_content)

        # Verify no more unapplied content changes
        unapplied_content_changes = stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
        )
        self.assertEqual(0, unapplied_content_changes.count())

    def test_deploy_compose_with_urls_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx",
            "user_content": DOCKER_COMPOSE_WEB_SERVICE,
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

        stack = cast(ComposeStack, ComposeStack.objects.filter(slug="nginx").first())
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.urls)

        # Deploy the stack
        response = self.client.post(
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
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify URLs are applied
        stack.refresh_from_db()
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("web", stack_urls)
        routes = cast(list, stack_urls["web"])
        self.assertEqual(len(routes), 1)
        route = cast(dict, routes[0])
        self.assertEqual("hello.127-0-0-1.sslip.io", route["domain"])
        self.assertEqual("/", route["base_path"])
        self.assertEqual(80, route["port"])

    def test_deploy_compose_with_configs_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx-inline-configs",
            "user_content": DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
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

        stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="nginx-inline-configs").first(),
        )
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.configs)

        # Deploy the stack
        response = self.client.post(
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
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify configs are applied
        stack.refresh_from_db()
        self.assertIsNotNone(stack.configs)
        stack_configs = cast(dict, stack.configs)
        self.assertIn("nginx_config", stack_configs)
        expected_content = (
            "user nginx;\n"
            "worker_processes auto;\n"
            "events {\n"
            "  worker_connections 1024;\n"
            "}"
        )
        self.assertEqual(expected_content, stack_configs["nginx_config"])

    def test_deploy_compose_with_env_overrides_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "placeholder-stack",
            "user_content": DOCKER_COMPOSE_WITH_PLACEHOLDERS,
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

        stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="placeholder-stack").first(),
        )
        self.assertIsNotNone(stack)
        self.assertEqual(0, stack.env_overrides.count())

        # Deploy the stack
        response = self.client.post(
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
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify env overrides are applied
        stack.refresh_from_db()
        self.assertEqual(5, stack.env_overrides.count())

        # Verify db service env overrides
        db_user = stack.env_overrides.filter(service="db", key="POSTGRES_USER").first()
        self.assertIsNotNone(db_user)
        db_password = stack.env_overrides.filter(
            service="db", key="POSTGRES_PASSWORD"
        ).first()
        self.assertIsNotNone(db_password)
        db_name = stack.env_overrides.filter(service="db", key="POSTGRES_DB").first()
        self.assertIsNotNone(db_name)

        # Verify app service env overrides
        app_token = stack.env_overrides.filter(service="app", key="API_TOKEN").first()
        self.assertIsNotNone(app_token)
        app_secret = stack.env_overrides.filter(service="app", key="SECRET_KEY").first()
        self.assertIsNotNone(app_secret)


class DeployComposeStackResourcesViewTests(ComposeStackAPITestBase):
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
        response = await self.async_client.post(
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
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

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

    async def test_deploy_compose_stack_create_resources(self):
        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)
        jprint(stack.service_statuses)
        jprint(deployment.stack_snapshot)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )
        self.assertIsNotNone(deployment.finished_at)

        # service statuses should be updated
        statuses = cast(dict, stack.service_statuses)
        self.assertGreater(len(statuses), 0)

        name, redis_service = next(iter(stack.service_statuses.items()))
        self.assertEqual("redis", name)
        self.assertEqual(ComposeStackServiceStatus.HEALTHY, redis_service["status"])
        self.assertEqual(1, redis_service["running_replicas"])
        self.assertEqual(1, redis_service["desired_replicas"])
        self.assertEqual(1, len(redis_service["tasks"]))

        # service should be created
        services: list[FakeDockerClient.FakeService] = []
        for service in statuses:
            try:
                services.append(
                    self.fake_docker_client.services_get(
                        f"{stack.name}_{stack.hash_prefix}_{service}"
                    )
                )
            except Exception:
                pass
        self.assertGreater(len(services), 0)

    async def test_deploy_compose_stack_with_inline_configs_creates_config_files(self):
        # Track config files written during deployment
        captured_config_files: dict[str, str] = {}

        original_create_files = (
            ComposeStackActivities.create_files_in_docker_stack_folder
        )

        @activity.defn(name="create_files_in_docker_stack_folder")
        async def capture_config_files_wrapper(self_instance, details: dict):
            build_details = ComposeStackBuildDetails.from_dict(details)

            # Call original implementation
            await original_create_files(self_instance, build_details)

            # Check for config files in tmp_build_dir
            tmp_dir = build_details.tmp_build_dir
            for filename in os.listdir(tmp_dir):
                if filename.endswith(".conf"):
                    filepath = os.path.join(tmp_dir, filename)
                    with open(filepath, "r") as f:
                        captured_config_files[filename] = f.read()

        with patch.object(
            ComposeStackActivities,
            "create_files_in_docker_stack_folder",
            capture_config_files_wrapper,
        ):
            _, stack = await self.acreate_and_deploy_compose_stack(
                content=DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
                slug="nginx-configs",
            )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify configs were applied to the stack
        self.assertIsNotNone(stack.configs)
        stack_configs = cast(dict, stack.configs)
        self.assertIn("nginx_config", stack_configs)

        # Verify the config content matches what was defined
        expected_content = (
            "user nginx;\n"
            "worker_processes auto;\n"
            "events {\n"
            "  worker_connections 1024;\n"
            "}"
        )
        self.assertEqual(expected_content, stack_configs["nginx_config"])

        # Verify config file was created with correct name format: {hash_prefix}_{config_name}.conf
        expected_filename = f"{stack.hash_prefix}_nginx_config.conf"
        self.assertIn(
            expected_filename,
            captured_config_files,
            f"Expected config file '{expected_filename}' to be created, got: {list(captured_config_files.keys())}",
        )

        # Verify file content matches
        self.assertEqual(expected_content, captured_config_files[expected_filename])

    @responses.activate()
    async def test_deploy_compose_stack_with_routes_exposes_to_http(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE,
            slug="nginx-routes",
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify URLs were applied to the stack
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("web", stack_urls)

        routes = cast(list, stack_urls["web"])
        self.assertEqual(len(routes), 1)

        route = cast(dict, routes[0])
        self.assertEqual("hello.127-0-0-1.sslip.io", route["domain"])
        self.assertEqual("/", route["base_path"])
        self.assertEqual(80, route["port"])

        # Verify the route was registered in Caddy
        # The route ID for compose stacks follows the pattern: stack_id-service_name-route_index
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(200, response.status_code)
        jprint(response.json())

    @responses.activate()
    async def test_deploy_compose_stack_with_multiple_routes(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MULTIPLE_ROUTES,
            slug="api-routes",
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify URLs were applied
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("api", stack_urls)

        routes = cast(list, stack_urls["api"])
        self.assertEqual(len(routes), 2)

        # Verify first route (api.example.com/)
        route_0 = cast(dict, routes[0])
        self.assertEqual("api.example.com", route_0["domain"])
        self.assertEqual("/", route_0["base_path"])

        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="api",
                url=ComposeStackUrlRouteDto.from_dict(route_0),
            )
        )
        self.assertEqual(200, response.status_code)
        jprint(response.json())

        # Verify second route (example.com/api)
        route_1 = cast(dict, routes[1])
        self.assertEqual("example.com", route_1["domain"])
        self.assertEqual("/api", route_1["base_path"])

        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="api",
                url=ComposeStackUrlRouteDto.from_dict(route_1),
            )
        )
        self.assertEqual(200, response.status_code)
        jprint(response.json())

    async def test_deploy_compose_stack_creates_healthcheck_schedule(self):
        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL,
            slug="healthcheck-stack",
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify the healthcheck schedule was created
        schedule_handle = self.get_workflow_schedule_by_id(stack.monitor_schedule_id)
        self.assertIsNotNone(schedule_handle)

    async def test_monitor_compose_stack_workflow_updates_service_statuses(self):
        async with self.workflowEnvironment() as env:
            _, stack = await self.acreate_and_deploy_compose_stack(
                content=DOCKER_COMPOSE_MINIMAL,
                slug="monitor-stack",
            )

            deployment = await stack.deployments.afirst()
            self.assertIsNotNone(deployment)
            deployment = cast(ComposeStackDeployment, deployment)

            self.assertEqual(
                ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
            )

            # Verify service statuses are initially set after deployment
            statuses = cast(dict, stack.service_statuses)
            self.assertGreater(len(statuses), 0)

            # Clear service statuses to simulate stale state
            stack.service_statuses = {}
            await stack.asave()

            # Refresh to verify it was cleared
            await stack.arefresh_from_db()
            self.assertEqual({}, stack.service_statuses)

            # Run the monitor workflow directly
            snapshot = ComposeStackSnapshot(
                id=stack.id,
                name=stack.name,
                slug=stack.slug,
                hash_prefix=stack.hash_prefix,
                monitor_schedule_id=stack.monitor_schedule_id,
                network_alias_prefix=stack.network_alias_prefix,
                user_content=stack.user_content or "",
                computed_content=stack.computed_content or "",
            )

            healthcheck = await env.client.execute_workflow(
                workflow=MonitorComposeStackWorkflow.run,
                arg=snapshot,
                id=stack.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )

            jprint(healthcheck.services)

            # Refresh and verify service statuses are updated
            await stack.arefresh_from_db()
            statuses = cast(dict, stack.service_statuses)
            self.assertGreater(len(statuses), 0)

            name, redis_service = next(iter(statuses.items()))
            self.assertEqual("redis", name)
            self.assertEqual(ComposeStackServiceStatus.HEALTHY, redis_service["status"])
            self.assertEqual(1, redis_service["running_replicas"])
            self.assertEqual(1, redis_service["desired_replicas"])
