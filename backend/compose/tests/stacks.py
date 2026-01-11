import base64
import uuid
from typing import Any, cast

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from zane_api.models import URL, Environment, Project
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import find_item_in_sequence, jprint

from ..models import ComposeStack, ComposeStackChange
from ..processor import ComposeSpecProcessor
from .fixtures import (
    DOCKER_COMPOSE_EXTERNAL_VOLUME,
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_MULTIPLE_ROUTES,
    DOCKER_COMPOSE_ROUTE_MISSING_DOMAIN,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_WITH_BASE64_GENERATE,
    DOCKER_COMPOSE_WITH_CUSTOM_PASSWORD_LENGTH,
    DOCKER_COMPOSE_WITH_DEPENDS_ON,
    DOCKER_COMPOSE_WITH_EXTERNAL_CONFIGS,
    DOCKER_COMPOSE_WITH_GENERATE_DOMAIN,
    DOCKER_COMPOSE_WITH_HOST_VOLUME,
    DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WITH_UUID_GENERATE,
    DOCKER_COMPOSE_WITH_X_ENV_IN_CONFIGS,
    DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
    DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES,
    INVALID_COMPOSE_EMPTY,
    INVALID_COMPOSE_EMPTY_SERVICES,
    INVALID_COMPOSE_NO_IMAGE,
    INVALID_COMPOSE_NO_SERVICES,
    INVALID_COMPOSE_RELATIVE_BIND_VOLUME,
    INVALID_COMPOSE_ROUTE_INVALID_PORT_NEGATIVE,
    INVALID_COMPOSE_ROUTE_INVALID_PORT_ZERO,
    INVALID_COMPOSE_ROUTE_MISSING_PORT,
    INVALID_COMPOSE_SERVICE_NAME_SPECIAL,
    INVALID_COMPOSE_SERVICES_NOT_DICT,
    INVALID_COMPOSE_WITH_CONFIG_FILE_LOCATION,
    INVALID_COMPOSE_X_ENV_NOT_DICT,
    INVALID_COMPOSE_YAML_SYNTAX,
    INVALID_DOCKER_COMPOSE_DUPLICATE_URLS,
    INVALID_DOCKER_COMPOSE_WIDLCARD_SHADOW_URLS,
    compose_with_url,
)


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

        # Verify that compile_stack_for_deployment generates correct computed values
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_MINIMAL,
            stack=created_stack,
        )
        self.assertIsNotNone(artifacts.computed_content)
        self.assertNotEqual(artifacts.computed_content, DOCKER_COMPOSE_MINIMAL.strip())
        print(
            "========= original =========",
            DOCKER_COMPOSE_MINIMAL.strip(),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
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

        # Verify compile_stack_for_deployment generates correct volume config
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_SIMPLE_DB,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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

        # Verify compile_stack_for_deployment generates correct host volume config
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_HOST_VOLUME,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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
        bind_volume = find_item_in_sequence(
            lambda v: v["type"] == "bind", service_volumes
        )
        bind_volume = cast(dict[str, Any], bind_volume)
        self.assertIsNotNone(bind_volume)
        self.assertIsInstance(bind_volume, dict)
        self.assertIsNotNone(bind_volume.get("source"))

        self.assertEqual("/var/run/docker.sock", bind_volume["source"])
        self.assertEqual("/var/run/docker.sock", bind_volume["target"])
        self.assertTrue(bind_volume.get("read_only"))

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

        # Verify compile_stack_for_deployment handles external volumes correctly
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_EXTERNAL_VOLUME,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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

        # Verify compile_stack_for_deployment generates correct URL config
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WEB_SERVICE,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
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

        self.assertIn("zane.http.routes.0.port", labels)
        self.assertEqual("80", labels["zane.http.routes.0.port"])

        self.assertIn("zane.http.routes.0.domain", labels)
        self.assertEqual(
            "hello.127-0-0-1.sslip.io", labels["zane.http.routes.0.domain"]
        )

        self.assertIn("zane.http.routes.0.base_path", labels)
        self.assertEqual("/", labels["zane.http.routes.0.base_path"])

        extracted_urls = artifacts.urls
        self.assertIsNotNone(extracted_urls)
        self.assertEqual(len(extracted_urls), 1)

        routes = extracted_urls["web"]
        self.assertEqual(len(routes), 1)

        route = routes[0]
        self.assertEqual(route.domain, "hello.127-0-0-1.sslip.io")
        self.assertEqual(route.base_path, "/")
        self.assertEqual(route.port, 80)
        self.assertTrue(route.strip_prefix)

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

        # Verify compile_stack_for_deployment generates correct multiple URLs
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_MULTIPLE_ROUTES,
            stack=created_stack,
        )
        extracted_urls = artifacts.urls
        self.assertIsNotNone(extracted_urls)
        self.assertEqual(len(extracted_urls), 1)

        routes = extracted_urls["api"]
        self.assertEqual(len(routes), 2)

        route_0 = routes[0]
        self.assertEqual(route_0.domain, "api.example.com")
        self.assertEqual(route_0.base_path, "/")
        self.assertEqual(route_0.port, 3000)
        self.assertFalse(route_0.strip_prefix)

        route_1 = routes[1]
        self.assertEqual(route_1.domain, "example.com")
        self.assertEqual(route_1.base_path, "/api")
        self.assertEqual(route_1.port, 3001)
        self.assertTrue(route_1.strip_prefix)

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

        # Verify compile_stack_for_deployment generates correct dependencies
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_DEPENDS_ON,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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
        Test that x-env placeholders are resolved by compile_stack_for_deployment.
        At creation time, only user_content is stored. No env_override changes are created.
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

        # Env override changes ARE created at creation time from compile_stack_for_deployment
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )
        self.assertEqual(5, env_changes.count())

        # Verify compile_stack_for_deployment resolves placeholders
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_PLACEHOLDERS,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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
        self.assertNotEqual("{{ generate_password | 64 }}", env["POSTGRES_PASSWORD"])
        self.assertNotEqual("${POSTGRES_PASSWORD}", env["POSTGRES_PASSWORD"])
        self.assertNotEqual("{{ generate_slug }}", env["POSTGRES_DB"])
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
        self.assertNotEqual("{{ generate_password | 32 }}", app_env["API_TOKEN"])
        self.assertNotEqual("${API_TOKEN}", app_env["API_TOKEN"])
        self.assertNotEqual("{{ generate_password | 64 }}", app_env["SECRET_KEY"])
        self.assertNotEqual("${SECRET_KEY}", app_env["SECRET_KEY"])

        # Verify env_overrides are generated by compile_stack_for_deployment
        self.assertEqual(5, len(artifacts.env_overrides))
        env_override_keys = {override.key for override in artifacts.env_overrides}
        expected_keys = {
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "API_TOKEN",
            "SECRET_KEY",
        }
        self.assertEqual(expected_keys, env_override_keys)

        # Verify all values are resolved (no templates or refs)
        for override in artifacts.env_overrides:
            self.assertIsNotNone(override.value)
            self.assertGreater(len(override.value), 0)
            self.assertNotEqual("{{ generate_username }}", override.value)
            self.assertNotEqual("{{ generate_password_32 }}", override.value)
            self.assertNotEqual("{{ generate_password_64 }}", override.value)
            self.assertNotEqual("{{ generate_slug }}", override.value)

    def test_create_compose_with_generate_domain_placeholder(self):
        """
        Test that {{ generate_domain }} placeholder generates a valid domain.
        At creation time, only user_content is stored. Placeholders resolved during deployment.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "domain-stack",
            "user_content": DOCKER_COMPOSE_WITH_GENERATE_DOMAIN,
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
            ComposeStack, ComposeStack.objects.filter(slug="domain-stack").first()
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

        # Env override changes ARE created at creation time (for APP_DOMAIN)
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )
        self.assertEqual(1, env_changes.count())

        # Verify compile_stack_for_deployment resolves generate_domain
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_GENERATE_DOMAIN,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        services = cast(dict, computed_dict.get("services"))

        # Find web service and verify APP_DOMAIN is resolved
        web_service = None
        for service_name, service_config in services.items():
            if service_name.endswith("_web"):
                web_service = service_config
                break

        self.assertIsNotNone(web_service)
        web_service = cast(dict, web_service)
        self.assertIn("environment", web_service)
        env = cast(dict, web_service.get("environment"))

        # Verify APP_DOMAIN was resolved to a subdomain of `ROOT_DOMAIN`
        self.assertIn("APP_DOMAIN", env)
        app_domain = env["APP_DOMAIN"]
        self.assertNotEqual("{{ generate_domain }}", app_domain)
        self.assertNotEqual("${APP_DOMAIN}", app_domain)
        self.assertIn(settings.ROOT_DOMAIN, app_domain)

        # Verify API_URL was resolved using the generated domain
        self.assertIn("API_URL", env)
        api_url = env["API_URL"]
        self.assertIn(app_domain, api_url)
        self.assertIn("/api", api_url)

        # Verify URL routes were extracted with the generated domain
        urls_data = artifacts.urls
        self.assertIsNotNone(urls_data)
        self.assertIn("web", urls_data)
        routes = urls_data["web"]
        self.assertEqual(1, len(routes))
        self.assertEqual(app_domain, routes[0].domain)

        # Verify env override was generated for APP_DOMAIN
        env_override_keys = {override.key for override in artifacts.env_overrides}
        self.assertIn("APP_DOMAIN", env_override_keys)

    def test_create_compose_with_generate_password_placeholder(self):
        """
        Test that {{ generate_password | <length> }} generates a password of the provided length.
        At creation time, only user_content is stored. Placeholders resolved during deployment.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "custom-length-stack",
            "user_content": DOCKER_COMPOSE_WITH_CUSTOM_PASSWORD_LENGTH,
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
            ComposeStack.objects.filter(slug="custom-length-stack").first(),
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

        # Verify compile_stack_for_deployment generates passwords of correct length
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_CUSTOM_PASSWORD_LENGTH,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        x_env = computed_dict.get("x-env", {})

        # Test generate_password_N
        self.assertIn("CUSTOM_PASSWORD_16", x_env)
        password_16 = x_env["CUSTOM_PASSWORD_16"]
        self.assertNotEqual("{{ generate_password | 16 }}", password_16)
        self.assertEqual(16, len(password_16))
        self.assertTrue(
            all(c.isalnum() or c in "+/=" for c in password_16),
            f"Password should be alphanumeric: {password_16}",
        )

        self.assertIn("CUSTOM_PASSWORD_128", x_env)
        password_128 = x_env["CUSTOM_PASSWORD_128"]
        self.assertNotEqual("{{ generate_password | 128 }}", password_128)
        self.assertEqual(128, len(password_128))
        self.assertTrue(
            all(c.isalnum() or c in "+/=" for c in password_128),
            f"Password should be alphanumeric: {password_128}",
        )

    def test_create_compose_with_generate_base64_placeholder(self):
        """
        Test that {{ generate_base64 | "value" }} encodes the given value to base64.
        At creation time, only user_content is stored. Placeholders resolved during deployment.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "base64-stack",
            "user_content": DOCKER_COMPOSE_WITH_BASE64_GENERATE,
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
            ComposeStack.objects.filter(slug="base64-stack").first(),
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

        # Verify compile_stack_for_deployment generates base64 values
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_BASE64_GENERATE,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        x_env = computed_dict.get("x-env", {})

        # Verify BASE64_HELLO is base64 encoded "hello"
        self.assertIn("BASE64_HELLO", x_env)
        base64_hello = x_env["BASE64_HELLO"]
        self.assertNotEqual("{{ generate_base64 | 'hello' }}", base64_hello)
        self.assertEqual(base64.b64encode(b"hello").decode(), base64_hello)

        # Verify BASE64_BYE is base64 encoded "bye"
        self.assertIn("BASE64_BYE", x_env)
        base64_bye = x_env["BASE64_BYE"]
        self.assertNotEqual("{{ generate_base64 | 'bye' }}", base64_bye)
        self.assertEqual(base64.b64encode(b"bye").decode(), base64_bye)

    def test_create_compose_with_generate_uuid_placeholder(self):
        """
        Test that {{ generate_uuid }} generates a valid UUID.
        At creation time, only user_content is stored. Placeholders resolved during deployment.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "uuid-stack",
            "user_content": DOCKER_COMPOSE_WITH_UUID_GENERATE,
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
            ComposeStack.objects.filter(slug="uuid-stack").first(),
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

        # Verify compile_stack_for_deployment generates UUIDs
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_UUID_GENERATE,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        x_env = computed_dict.get("x-env", {})

        # Verify LICENCE_ID is a valid UUID
        self.assertIn("LICENCE_ID", x_env)
        licence_id = x_env["LICENCE_ID"]
        self.assertNotEqual("{{ generate_uuid }}", licence_id)

        # Validate using uuid.UUID - raises ValueError if invalid
        try:
            uuid.UUID(licence_id)
        except ValueError:
            self.fail(f"LICENCE_ID should be a valid UUID, got: {licence_id}")

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

        # Verify compile_stack_for_deployment handles external configs
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_EXTERNAL_CONFIGS,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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

        # Verify compile_stack_for_deployment handles inline configs
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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

        configs_data = artifacts.configs
        self.assertIsNotNone(configs_data)
        self.assertIn("nginx_config", configs_data)

        expected_content = (
            "user nginx;\n"
            "worker_processes auto;\n"
            "events {\n"
            "  worker_connections 1024;\n"
            "}\n"
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
        self.assertIsNotNone(
            self.get_error_from_response(
                response, "services.web.deploy.labels.zane.http.routes.0.port"
            )
        )

    def test_create_compose_stack_with_route_missing_domain_do_not_create_route(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "missing-domain",
            "user_content": DOCKER_COMPOSE_ROUTE_MISSING_DOMAIN,
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
            ComposeStack, ComposeStack.objects.filter(slug="missing-domain").first()
        )
        self.assertIsNotNone(stack)

        pending_change = cast(
            ComposeStackChange,
            stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)

        # Verify compile_stack_for_deployment generates empty URLs when domain missing
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_ROUTE_MISSING_DOMAIN,
            stack=stack,
        )
        self.assertEqual(artifacts.urls, {})

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
        self.assertIsNotNone(
            self.get_error_from_response(
                response, "services.web.deploy.labels.zane.http.routes.0.port"
            )
        )

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
        self.assertIsNotNone(
            self.get_error_from_response(
                response, "services.web.deploy.labels.zane.http.routes.0.port"
            )
        )

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

        # Verify compile_stack_for_deployment generates network aliases
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_MINIMAL,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        services = cast(dict, computed_dict.get("services"))

        # Find the redis service
        _, redis_service = next(iter(services.items()))

        # Check networks configuration
        self.assertIn("networks", redis_service)
        networks = cast(dict, redis_service.get("networks"))

        # Should have zane network (no aliases)
        self.assertIn("zane", networks)
        self.assertIsNotNone(networks["zane"])

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
        1. At creation time, only user_content is stored (no env_override changes)
        2. compile_stack_for_deployment resolves placeholders and creates env_overrides
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

        # Env override changes ARE created at creation time (for generated passwords)
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )
        self.assertEqual(2, env_changes.count())

        # Verify compile_stack_for_deployment resolves x-env properly
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES,
            stack=created_stack,
        )
        computed_dict = artifacts.computed_spec

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

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
        self.assertNotEqual("{{ generate_password | 64 }}", db_env["POSTGRES_PASSWORD"])

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

        # Verify env_overrides are generated by compile_stack_for_deployment
        # Should have exactly 2 env overrides (for generated variables only)
        self.assertEqual(2, len(artifacts.env_overrides))

        env_override_keys = {override.key for override in artifacts.env_overrides}
        expected_keys = {
            "SERVICE_PASSWORD_POSTGRES",
            "SERVICE_PASSWORD_REDIS",
        }
        self.assertEqual(expected_keys, env_override_keys)

        # Verify generated values are not templates
        for override in artifacts.env_overrides:
            self.assertNotEqual("{{ generate_password_64 }}", override.value)
            self.assertIsNotNone(override.value)
            self.assertGreater(len(override.value), 0)

        # Verify x-env values in computed spec
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
            "{{ generate_password_64 }}", x_env["SERVICE_PASSWORD_POSTGRES"]
        )
        self.assertNotEqual(
            "{{ generate_password_64 }}", x_env["SERVICE_PASSWORD_REDIS"]
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
        self.assertIsNotNone(self.get_error_from_response(response, "x_env"))

    def test_create_compose_with_x_env_in_config_content(self):
        """
        Test that x-env variables are resolved in inline config content.
        Variables like ${APP_PORT} in config file content should be substituted.
        At creation time, only user_content is stored. Placeholders resolved during deployment.
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

        # Verify compile_stack_for_deployment resolves x-env in configs
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_X_ENV_IN_CONFIGS,
            stack=created_stack,
        )

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        # Get the resolved config content from artifacts
        configs_data = artifacts.configs
        self.assertIsNotNone(configs_data)
        self.assertIn("app_config", configs_data)

        config_content = configs_data["app_config"]

        # Verify static values are substituted in config content
        self.assertIn("listen 8080;", config_content)
        self.assertIn("server_name app.example.com;", config_content)
        self.assertIn("proxy_pass http://app.example.com:8080;", config_content)
        self.assertIn('X-App-Name "myapp"', config_content)

        # Verify generated password is substituted (not the template)
        self.assertNotIn("{{ generate_password | 64 }}", config_content)
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
        At creation time, only user_content is stored. Placeholders resolved during deployment.
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

        # Verify compile_stack_for_deployment resolves x-env in URLs
        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
            stack=created_stack,
        )

        print(
            "========= original =========",
            new_value.get("user_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            artifacts.computed_content,
            sep="\n",
        )

        # Get the resolved URLs from artifacts
        urls_data = artifacts.urls
        self.assertIsNotNone(urls_data)

        # Verify api service URL is resolved
        self.assertIn("api", urls_data)
        api_routes = urls_data["api"]
        self.assertEqual(1, len(api_routes))
        self.assertEqual("api.myapp.com", api_routes[0].domain)
        self.assertEqual(3000, api_routes[0].port)

        # Verify dashboard service URL is resolved
        self.assertIn("dashboard", urls_data)
        dashboard_routes = urls_data["dashboard"]
        self.assertEqual(1, len(dashboard_routes))
        self.assertEqual("dashboard.myapp.com", dashboard_routes[0].domain)
        self.assertEqual(8080, dashboard_routes[0].port)


class ComposeStackURLConflictTests(ComposeStackAPITestBase):
    """Tests for URL conflict validation in compose stacks."""

    def test_create_compose_stack_url_conflicts_with_existing_service_url(self):
        """
        Creating a compose stack with a URL that is already used by an existing
        docker service should fail with a validation error.
        """
        project, service = self.create_and_deploy_caddy_docker_service()

        url = cast(URL, service.urls.first())

        # Now try to create a compose stack with the same URL
        create_stack_payload = {
            "slug": "conflicting-stack",
            "user_content": compose_with_url(url.domain),
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

    def test_create_compose_stack_url_different_path_succeeds(self):
        """
        Creating a compose stack with a URL that has the same domain but
        different base_path should succeed.
        """
        project, service = self.create_and_deploy_caddy_docker_service()

        url = cast(URL, service.urls.first())

        # Try to create a compose stack with same domain but different path
        create_stack_payload = {
            "slug": "web-stack",
            "user_content": compose_with_url(url.domain, base_path="/web"),
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

    def test_create_compose_stack_url_conflicts_with_another_compose_stack(self):
        """
        Creating a compose stack with a URL that is already used by another
        deployed compose stack should fail.
        """
        project = self.create_project()

        # First create and deploy a compose stack with a URL
        first_stack_payload = {
            "slug": "first-stack",
            "user_content": compose_with_url("shared-domain.example.com"),
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=first_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Deploy the first stack so its URLs are applied
        first_stack = ComposeStack.objects.get(slug="first-stack")
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": first_stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Now try to create a second stack with the same URL
        second_stack_payload = {
            "slug": "second-stack",
            "user_content": compose_with_url("shared-domain.example.com"),
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=second_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_compose_stack_url_shadowed_by_wildcard_domain(self):
        """
        Creating a compose stack with a subdomain URL should fail if a wildcard
        domain is already assigned to another service.
        """
        project, _ = self.create_and_deploy_caddy_docker_service(
            domain="*.wildcard.example.com"
        )

        # Try to create a compose stack with a subdomain that would be shadowed
        create_stack_payload = {
            "slug": "subdomain-stack",
            "user_content": compose_with_url("api.wildcard.example.com"),
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

    def test_create_compose_stack_with_duplicate_urls_in_same_stack(self):
        """
        Creating a compose stack with duplicate URLs declared within the same
        compose file (e.g., two services with the same domain/path) should fail.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "duplicate-stack",
            "user_content": INVALID_DOCKER_COMPOSE_DUPLICATE_URLS,
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

    def test_create_compose_stack_with_wildcard_in_same_stack(self):
        """
        Creating a compose stack with duplicate URLs declared within the same
        compose file (e.g., two services with the same domain/path) should fail.
        """
        project = self.create_project()

        create_stack_payload = {
            "slug": "duplicate-stack",
            "user_content": INVALID_DOCKER_COMPOSE_WIDLCARD_SHADOW_URLS,
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
