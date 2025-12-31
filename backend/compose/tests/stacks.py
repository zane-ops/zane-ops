from django.urls import reverse
from rest_framework import status

from zane_api.models import Project, Environment
from zane_api.tests.base import AuthAPITestCase
from ..models import ComposeStack, ComposeStackChange
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
    DOCKER_COMPOSE_COMPREHENSIVE,
    INVALID_COMPOSE_WITH_BUILD,
    INVALID_COMPOSE_NO_IMAGE,
    INVALID_COMPOSE_SERVICE_NAME_DIGIT,
    INVALID_COMPOSE_SERVICE_NAME_UPPERCASE,
    INVALID_COMPOSE_RELATIVE_BIND_VOLUME,
    INVALID_COMPOSE_SERVICE_NAME_SPECIAL,
    INVALID_COMPOSE_YAML_SYNTAX,
    INVALID_COMPOSE_EMPTY,
    INVALID_COMPOSE_NO_SERVICES,
    INVALID_COMPOSE_SERVICES_NOT_DICT,
)
from typing import Any, cast
from zane_api.utils import jprint, find_item_in_sequence


class ComposeStackAPITestBase(AuthAPITestCase):
    def create_project(self, slug="my-project"):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": slug},
        )
        # 409 = project already created
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )
        return Project.objects.get(slug=slug)


class CreateComposeStackViewTests(ComposeStackAPITestBase):
    def test_create_simple_compose_stack(self):
        project = self.create_project()

        # Create compose stack
        create_stack_payload = {
            "slug": "my-stack",
            "user_compose_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="my-stack").first()
        )
        self.assertIsNotNone(created_stack)
        self.assertIsNone(created_stack.user_compose_content)
        self.assertIsNone(created_stack.computed_compose_content)

        # Verify that a change in progress has been created
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
            new_value.get("user_compose_content"),
            DOCKER_COMPOSE_MINIMAL.strip(),
        )
        self.assertIsNotNone(new_value.get("computed_compose_content"))
        self.assertNotEqual(
            new_value.get("computed_compose_content"),
            DOCKER_COMPOSE_MINIMAL.strip(),
        )
        print(
            "========= original =========",
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

    def test_create_compose_stack_with_volumes(self):
        project = self.create_project()

        # Create compose stack with volumes
        create_stack_payload = {
            "slug": "db-stack",
            "user_compose_content": DOCKER_COMPOSE_SIMPLE_DB,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="db-stack").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change contains volume configuration
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify volumes are in computed config
        self.assertIn("volumes", computed_dict)

        # verify that volumes have zaneops labels
        _, initial_volume = next(iter(computed_dict["volumes"].items()))
        self.assertIsNotNone(initial_volume.get("labels"))
        self.assertIn("zane-managed", initial_volume.get("labels"))
        self.assertIn("zane-stack", initial_volume.get("labels"))
        self.assertIn("zane-project", initial_volume.get("labels"))

        # Volume references in services should be preserved during reconciliation
        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        # Find the db service (it will have a hashed name like "abc123_db")
        service_name, service_config = next(iter(services.items()))
        self.assertNotEqual("postgres", service_name)
        self.assertTrue(service_name.endswith("postgres"))

        db_service = cast(dict, service_config)

        # Verify the service has volumes configured
        self.assertIn("volumes", db_service)
        service_volumes: list[dict[str, Any]] = cast(list, db_service.get("volumes"))
        self.assertGreater(len(service_volumes), 0, "Service should have volume mounts")

        # Verify volume is formatted correctly
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

        # Create compose stack with volumes
        create_stack_payload = {
            "slug": "portainer",
            "user_compose_content": DOCKER_COMPOSE_WITH_HOST_VOLUME,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="portainer").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change contains volume configuration
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify that no volumes are created in computed config
        self.assertNotIn("volumes", computed_dict)

        # Volume references in services should be preserved during reconciliation
        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        # Find the portainer service (it will have a hashed name like "abc123_portainer")
        _, service_config = next(iter(services.items()))
        portainer_service = cast(dict, service_config)

        # Verify the service has volumes configured
        self.assertIn("volumes", portainer_service)
        service_volumes: list[dict[str, Any]] = cast(
            list, portainer_service.get("volumes")
        )
        self.assertGreater(len(service_volumes), 0, "Service should have volume mounts")

        # Verify volume is formatted correctly
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

        # Create compose stack with volumes
        create_stack_payload = {
            "slug": "myapp",
            "user_compose_content": DOCKER_COMPOSE_EXTERNAL_VOLUME,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="myapp").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change contains volume configuration
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify that no volumes are created in computed config
        self.assertIn("volumes", computed_dict)

        # verify that volumes do not have zaneops labels
        name, initial_volume = next(iter(computed_dict["volumes"].items()))
        self.assertIsNone(initial_volume.get("labels"))
        self.assertEqual("shared_data", name)
        self.assertEqual({"external": True}, initial_volume)

        # Volume references in services should be preserved during reconciliation
        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        # Find the db service (it will have a hashed name like "abc123_db")
        _, service_config = next(iter(services.items()))
        app_service = cast(dict, service_config)

        # Verify the service has volumes configured
        self.assertIn("volumes", app_service)
        service_volumes: list[dict[str, Any]] = cast(list, app_service.get("volumes"))

        # Verify volume is formatted correctly
        volume = find_item_in_sequence(lambda v: v["type"] == "volume", service_volumes)
        volume = cast(dict[str, Any], volume)
        self.assertIsNotNone(volume)
        self.assertEqual("shared_data", volume["source"])

    def test_create_compose_stack_with_url(self):
        project = self.create_project()

        # Create compose stack with volumes
        create_stack_payload = {
            "slug": "nginx",
            "user_compose_content": DOCKER_COMPOSE_WEB_SERVICE,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="nginx").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change contains volume configuration
        computed_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(computed_change)

        # Get computed compose dict
        computed_dict = cast(
            dict, cast(dict, computed_change.new_value).get("computed_compose_dict")
        )
        self.assertIsNotNone(computed_dict)

        print(
            "========= original =========",
            cast(dict, computed_change.new_value).get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            cast(dict, computed_change.new_value).get("computed_compose_content"),
            sep="\n",
        )

        # Verify services exist
        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)

        # Find the web service (it will have a hashed name like "abc123_web")
        _, service_config = next(iter(services.items()))
        web_service = cast(dict, service_config)

        # Verify the service has HTTP exposure labels in deploy config
        self.assertIn("deploy", web_service)
        deploy_config = cast(dict, web_service.get("deploy"))
        self.assertIn("labels", deploy_config)

        labels = cast(dict, deploy_config.get("labels"))

        # Verify HTTP port is configured
        self.assertIn("zane.http.port", labels)
        self.assertEqual("80", labels["zane.http.port"])

        # Verify HTTP route labels are present
        self.assertIn("zane.http.routes.0.domain", labels)
        self.assertEqual(
            "hello.127-0-0-1.sslip.io", labels["zane.http.routes.0.domain"]
        )

        self.assertIn("zane.http.routes.0.base_path", labels)
        self.assertEqual("/", labels["zane.http.routes.0.base_path"])

        # Verify pending change contains urls change
        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.URLS,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        # Verify extracted_urls field contains the parsed URL configuration
        extracted_urls = cast(dict, new_value)
        self.assertIsNotNone(extracted_urls)

        # The extracted_urls should be a dict mapping service names to route configs
        # Since service names are hashed, we need to find the web service by checking keys
        self.assertEqual(len(extracted_urls), 1, "Should have one service with URLs")

        # Verify the route configuration
        routes = cast(list, extracted_urls["web"])
        self.assertEqual(len(routes), 1, "Should have one route")

        route = cast(dict, routes[0])
        self.assertEqual(route["domain"], "hello.127-0-0-1.sslip.io")
        self.assertEqual(route["base_path"], "/")
        self.assertEqual(route["port"], 80)
        self.assertTrue(route["strip_prefix"], "strip_prefix should default to true")

    def test_create_compose_stack_with_multiple_urls(self):
        project = self.create_project()

        # Create compose stack with multiple routes
        create_stack_payload = {
            "slug": "api-stack",
            "user_compose_content": DOCKER_COMPOSE_MULTIPLE_ROUTES,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="api-stack").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change
        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.URLS,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        # Verify extracted_urls field contains both routes
        extracted_urls = cast(dict, new_value)
        self.assertIsNotNone(extracted_urls)

        # Should have one service with URLs
        self.assertEqual(len(extracted_urls), 1, "Should have one service with URLs")

        # Verify the route configurations
        routes = cast(list, extracted_urls["api"])
        self.assertEqual(len(routes), 2, "Should have two routes")

        # Verify first route
        route_0 = cast(dict, routes[0])
        self.assertEqual(route_0["domain"], "api.example.com")
        self.assertEqual(route_0["base_path"], "/")
        self.assertEqual(route_0["port"], 3000)
        self.assertFalse(
            route_0["strip_prefix"], "strip_prefix should be false for route 0"
        )

        # Verify second route
        route_1 = cast(dict, routes[1])
        self.assertEqual(route_1["domain"], "example.com")
        self.assertEqual(route_1["base_path"], "/api")
        self.assertEqual(route_1["port"], 3000)
        self.assertTrue(
            route_1["strip_prefix"], "strip_prefix should be true for route 1"
        )

    def test_create_compose_stack_with_dependencies(self):
        project = self.create_project()

        # Create compose stack with service dependencies
        create_stack_payload = {
            "slug": "django-app",
            "user_compose_content": DOCKER_COMPOSE_WITH_DEPENDS_ON,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify stack was created
        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="django-app").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify all three services exist
        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)
        self.assertEqual(len(services), 3, "Should have 3 services: web, db, cache")

        # Find the web service (it will have a hashed name like "abc123_web")
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

        # Verify the web service has depends_on preserved
        self.assertIn("depends_on", web_service, "Web service should have depends_on")
        depends_on = cast(list[str], web_service.get("depends_on"))
        self.assertEqual(len(depends_on), 2, "Web service should depend on 2 services")

        # Verify depends_on contains the original service names (not hashed)
        # The reconciliation should preserve user-specified fields like depends_on
        db_dependency = find_item_in_sequence(lambda d: d.endswith("_db"), depends_on)
        cache_dependency = find_item_in_sequence(
            lambda d: d.endswith("_cache"), depends_on
        )
        self.assertIsNotNone(db_dependency)
        self.assertIsNotNone(cache_dependency)

    def test_create_compose_with_env_placeholders(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "placeholder-stack",
            "user_compose_content": DOCKER_COMPOSE_WITH_PLACEHOLDERS,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
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

        # Verify placeholders were computed/generated
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        services = cast(dict, computed_dict.get("services"))

        # Find db service
        db_service = None
        for service_name, service_config in services.items():
            if service_name.endswith("_db"):
                db_service = service_config
                break

        self.assertIsNotNone(db_service)
        db_service = cast(dict, db_service)
        self.assertIn("environment", db_service)
        env = cast(dict, db_service.get("environment"))

        # Placeholders should be replaced with generated values
        self.assertIn("POSTGRES_USER", env)
        self.assertIn("POSTGRES_PASSWORD", env)
        self.assertIn("POSTGRES_DB", env)

        # Verify values are not the placeholder templates
        self.assertNotEqual("{{generate_username}}", env["POSTGRES_USER"])
        self.assertNotEqual("{{ generate_secure_password}}", env["POSTGRES_PASSWORD"])
        self.assertNotEqual("{{ generate_random_slug }}", env["POSTGRES_DB"])

        # Find app service and verify its placeholders
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
        self.assertNotEqual("{{ generate_random_chars_64 }}", app_env["SECRET_KEY"])

        # Verify env override changes were created for generated values
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )
        self.assertEqual(5, env_changes.count(), "Should have 5 env override changes")

        # Verify db service env overrides
        db_user_change = cast(
            ComposeStackChange,
            env_changes.filter(
                new_value__key="POSTGRES_USER",
                new_value__service="db",
            ).first(),
        )
        self.assertIsNotNone(db_user_change)
        self.assertEqual("db", cast(dict, db_user_change.new_value).get("service"))
        self.assertEqual(
            "POSTGRES_USER", cast(dict, db_user_change.new_value).get("key")
        )

        db_password_change = cast(
            ComposeStackChange,
            env_changes.filter(
                new_value__key="POSTGRES_PASSWORD",
                new_value__service="db",
            ).first(),
        )
        self.assertIsNotNone(db_password_change)
        self.assertEqual("db", cast(dict, db_password_change.new_value).get("service"))
        self.assertEqual(
            "POSTGRES_PASSWORD", cast(dict, db_password_change.new_value).get("key")
        )

        db_db_change = cast(
            ComposeStackChange,
            env_changes.filter(
                new_value__key="POSTGRES_DB",
                new_value__service="db",
            ).first(),
        )
        self.assertIsNotNone(db_db_change)
        self.assertEqual("db", cast(dict, db_db_change.new_value).get("service"))
        self.assertEqual("POSTGRES_DB", cast(dict, db_db_change.new_value).get("key"))

        # Verify app service env overrides
        app_token_change = cast(
            ComposeStackChange,
            env_changes.filter(
                new_value__key="API_TOKEN",
                new_value__service="app",
            ).first(),
        )
        self.assertIsNotNone(app_token_change)
        self.assertEqual("app", cast(dict, app_token_change.new_value).get("service"))
        self.assertEqual("API_TOKEN", cast(dict, app_token_change.new_value).get("key"))

        app_secret_change = cast(
            ComposeStackChange,
            env_changes.filter(
                new_value__key="SECRET_KEY",
                new_value__service="app",
            ).first(),
        )
        self.assertIsNotNone(app_secret_change)
        self.assertEqual("app", cast(dict, app_secret_change.new_value).get("service"))
        self.assertEqual(
            "SECRET_KEY", cast(dict, app_secret_change.new_value).get("key")
        )

    def test_create_compose_stack_with_external_configs(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx-external-configs",
            "user_compose_content": DOCKER_COMPOSE_WITH_EXTERNAL_CONFIGS,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
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

        # Verify pending change
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify configs section exists
        self.assertIn("configs", computed_dict)
        configs = cast(dict, computed_dict["configs"])

        # Verify external configs are preserved without modification (no labels)
        self.assertIn("nginx_config", configs)
        self.assertIn("site_config", configs)
        self.assertEqual({"external": True}, configs["nginx_config"])
        self.assertEqual({"external": True}, configs["site_config"])

        # Verify service has configs mounted
        services = cast(dict, computed_dict.get("services"))
        _, service_config = next(iter(services.items()))
        web_service = cast(dict, service_config)

        self.assertIn("configs", web_service)
        service_configs = cast(list, web_service.get("configs"))
        self.assertEqual(len(service_configs), 2)

        # Verify config mounts are preserved
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
            "user_compose_content": DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
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

        # Verify pending change
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
            new_value.get("user_compose_content"),
            sep="\n",
        )
        print(
            "========= computed =========",
            new_value.get("computed_compose_content"),
            sep="\n",
        )

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify configs section exists
        self.assertIn("configs", computed_dict)
        configs = cast(dict, computed_dict["configs"])

        # Verify inline configs are preserved
        self.assertIn("nginx_config", configs)
        self.assertIn("app_settings", configs)

        # Verify content-based config has ZaneOps labels
        nginx_config = cast(dict, configs["nginx_config"])
        self.assertIn("content", nginx_config)
        self.assertIn("user nginx", nginx_config["content"])
        self.assertIn("worker_processes auto", nginx_config["content"])

        # Verify inline configs have zaneops labels
        nginx_config_labels = nginx_config.get("labels")
        self.assertIsNotNone(nginx_config_labels)
        nginx_config_labels = cast(dict, nginx_config_labels)
        self.assertIn("zane-managed", nginx_config_labels)
        self.assertIn("zane-stack", nginx_config_labels)
        self.assertIn("zane-project", nginx_config_labels)

        # Verify file-based config has ZaneOps labels
        app_settings = cast(dict, configs["app_settings"])
        self.assertIn("file", app_settings)
        self.assertEqual("./config/settings.json", app_settings["file"])

        # Verify inline configs have zaneops labels
        app_settings_labels = app_settings.get("labels")
        self.assertIsNotNone(app_settings_labels)
        app_settings_labels = cast(dict, app_settings_labels)
        self.assertIn("zane-managed", app_settings_labels)
        self.assertIn("zane-stack", app_settings_labels)
        self.assertIn("zane-project", app_settings_labels)

        # Verify service has configs mounted
        services = cast(dict, computed_dict.get("services"))
        _, service_config = next(iter(services.items()))
        web_service = cast(dict, service_config)

        self.assertIn("configs", web_service)
        service_configs = cast(list, web_service.get("configs"))
        self.assertEqual(len(service_configs), 2)

        # Verify config mounts are preserved
        nginx_config_mount = find_item_in_sequence(
            lambda c: c["source"] == "nginx_config", service_configs
        )
        app_settings_mount = find_item_in_sequence(
            lambda c: c["source"] == "app_settings", service_configs
        )

        self.assertIsNotNone(nginx_config_mount)
        self.assertIsNotNone(app_settings_mount)
        self.assertEqual(
            "/etc/nginx/nginx.conf", cast(dict, nginx_config_mount).get("target")
        )
        self.assertEqual(
            "/app/config.json", cast(dict, app_settings_mount).get("target")
        )

    def test_create_compose_stack_comprehensive(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "comprehensive-stack",
            "user_compose_content": DOCKER_COMPOSE_COMPREHENSIVE,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
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
            ComposeStack.objects.filter(slug="comprehensive-stack").first(),
        )
        self.assertIsNotNone(created_stack)

        # Verify pending change
        pending_change = cast(
            ComposeStackChange,
            created_stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
            ).first(),
        )
        self.assertIsNotNone(pending_change)
        new_value = cast(dict, pending_change.new_value)

        # Get computed compose dict
        computed_dict = cast(dict, new_value.get("computed_compose_dict"))
        self.assertIsNotNone(computed_dict)

        # Verify all services exist
        services = cast(dict, computed_dict.get("services"))
        self.assertIsNotNone(services)
        self.assertEqual(
            len(services), 5, "Should have 5 services: frontend, api, db, cache, worker"
        )

        # Verify volumes exist
        self.assertIn("volumes", computed_dict)
        volumes = cast(dict, computed_dict["volumes"])
        self.assertGreater(len(volumes), 0)

        # Verify networks exist (should have zane, env network, and custom network)
        self.assertIn("networks", computed_dict)
        networks = cast(dict, computed_dict["networks"])
        self.assertIn("zane", networks)

    def test_create_compose_stack_with_build_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "build-stack",
            "user_compose_content": INVALID_COMPOSE_WITH_BUILD,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_without_image_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "no-image-stack",
            "user_compose_content": INVALID_COMPOSE_NO_IMAGE,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_service_name_starting_with_digit_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "digit-service-name",
            "user_compose_content": INVALID_COMPOSE_SERVICE_NAME_DIGIT,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_uppercase_service_name_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "uppercase-service-name",
            "user_compose_content": INVALID_COMPOSE_SERVICE_NAME_UPPERCASE,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_relative_bind_volume_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "relative-bind-volume",
            "user_compose_content": INVALID_COMPOSE_RELATIVE_BIND_VOLUME,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_special_char_service_name_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "special-char-service",
            "user_compose_content": INVALID_COMPOSE_SERVICE_NAME_SPECIAL,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_invalid_yaml_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "invalid-yaml",
            "user_compose_content": INVALID_COMPOSE_YAML_SYNTAX,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_empty_content_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "empty-compose",
            "user_compose_content": INVALID_COMPOSE_EMPTY,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_no_services_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "no-services",
            "user_compose_content": INVALID_COMPOSE_NO_SERVICES,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())

    def test_create_compose_stack_with_services_as_list_fails(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "services-list",
            "user_compose_content": INVALID_COMPOSE_SERVICES_NOT_DICT,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("user_compose_content", response.json())
