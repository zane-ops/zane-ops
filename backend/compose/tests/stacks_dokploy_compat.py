from typing import cast

from django.urls import reverse
from rest_framework import status
import yaml
from zane_api.models import Environment
from zane_api.utils import jprint

from ..models import ComposeStack, ComposeStackChange
from .fixtures import DOKPLOY_POCKETBASE_TEMPLATE, DOKPLOY_VALKEY_TEMPLATE
from .stacks import ComposeStackAPITestBase


class DokployCompatibilityViewTests(ComposeStackAPITestBase):
    def test_create_compose_stack_from_dokploy(self):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "my-stack",
            "user_content": DOKPLOY_POCKETBASE_TEMPLATE.base64,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create_from_dokploy",
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
        new_value = cast(str, pending_change.new_value)
        self.assertIsNotNone(new_value)
        print("========= converted user_content =========")
        print(new_value)

        # Parse the converted user_content to verify it was transformed correctly
        user_content_dict = yaml.safe_load(new_value)

        # Verify x-env section was added with template placeholders
        self.assertIn("x-env", user_content_dict)
        x_env = user_content_dict["x-env"]

        # Check that the dokploy variables were converted to x-env with template expressions
        self.assertIn("main_domain", x_env)
        self.assertIn("admin_email", x_env)
        self.assertIn("admin_password", x_env)
        self.assertIn("ADMIN_EMAIL", x_env)
        self.assertIn("ADMIN_PASSWORD", x_env)

        # Verify template expressions are used (not plain values)
        self.assertEqual("{{ generate_domain }}", x_env["main_domain"])
        self.assertEqual("{{ generate_email }}", x_env["admin_email"])
        self.assertEqual("{{ generate_password | 32 }}", x_env["admin_password"])

        # Verify services section exists
        self.assertIn("services", user_content_dict)
        services = user_content_dict["services"]
        self.assertIn("pocketbase", services)

        pocketbase_service = services["pocketbase"]

        # Verify environment variables reference x-env variables
        self.assertIn("environment", pocketbase_service)

        # Verify deploy labels for URL routing were added
        self.assertIn("deploy", pocketbase_service)
        deploy = pocketbase_service["deploy"]
        self.assertIn("labels", deploy)
        labels = deploy["labels"]

        # Check URL routing labels (from dokploy config domains section)
        self.assertIn("zane.http.routes.0.domain", labels)
        self.assertIn("zane.http.routes.0.port", labels)
        self.assertIn("zane.http.routes.0.base_path", labels)

        # Verify the domain uses x-env reference
        self.assertEqual("${main_domain}", labels["zane.http.routes.0.domain"])
        self.assertEqual(8090, labels["zane.http.routes.0.port"])
        self.assertEqual("/", labels["zane.http.routes.0.base_path"])

    def test_create_compose_stack_from_dokploy_creates_env_override_changes(self):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "my-stack-2",
            "user_content": DOKPLOY_POCKETBASE_TEMPLATE.base64,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create_from_dokploy",
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
            ComposeStack, ComposeStack.objects.filter(slug="my-stack-2").first()
        )
        self.assertIsNotNone(created_stack)

        # Verify env override changes are created for template placeholders
        env_changes = created_stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
            type=ComposeStackChange.ChangeType.ADD,
        )

        # Should have ADD changes for placeholders: main_domain, admin_email, admin_password
        self.assertEqual(3, env_changes.count())

        env_override_keys = {
            cast(dict, change.new_value)["key"] for change in env_changes
        }
        expected_keys = {
            "main_domain",
            "admin_email",
            "admin_password",
        }
        self.assertEqual(expected_keys, env_override_keys)

    def test_create_compose_stack_from_dokploy_with_removes_exposed_ports(
        self,
    ):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "valkey-no-ports",
            "user_content": DOKPLOY_VALKEY_TEMPLATE.base64,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create_from_dokploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="valkey-no-ports").first()
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
        new_value = cast(str, pending_change.new_value)

        # Parse the converted user_content
        user_content_dict = yaml.safe_load(new_value)

        # Verify services section exists
        services = user_content_dict["services"]
        self.assertIn("valkey", services)
        valkey_service = services["valkey"]

        # Verify that exposed ports are removed
        # Original compose had: ports: - 6379
        # This should be removed in the converted compose
        self.assertNotIn("ports", valkey_service)

    def test_create_compose_stack_from_dokploy_with_config_content_is_transformed_into_inline_content(
        self,
    ):
        project = self.create_project(slug="compose")

        create_stack_payload = {
            "slug": "vakey",
            "user_content": DOKPLOY_VALKEY_TEMPLATE.base64,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create_from_dokploy",
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
            ComposeStack, ComposeStack.objects.filter(slug="vakey").first()
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
        new_value = cast(str, pending_change.new_value)
        self.assertIsNotNone(new_value)

        # Parse the converted user_content
        user_content_dict = yaml.safe_load(new_value)

        # Verify configs section exists with inline content
        self.assertIn("configs", user_content_dict)
        configs = user_content_dict["configs"]
        self.assertIn("valkey.conf", configs)

        valkey_config = configs["valkey.conf"]

        # Verify it has content field (not file field)
        self.assertIn("content", valkey_config)
        self.assertNotIn("file", valkey_config)

        # Verify the content includes the password placeholder reference
        content = valkey_config["content"]
        self.assertIsNotNone(content)
        self.assertIn("requirepass ${valkey_password}", content)
        self.assertIn("bind 0.0.0.0", content)
        self.assertIn("port 6379", content)

        # Verify the service uses the config
        services = user_content_dict["services"]
        self.assertIn("valkey", services)
        valkey_service = services["valkey"]

        # Verify the service removes the local env
        services = user_content_dict["services"]
        self.assertIn("valkey", services)
        valkey_service = services["valkey"]

        # Check that configs reference is present
        self.assertIn("configs", valkey_service)
        service_configs = valkey_service["configs"]
        self.assertTrue(len(service_configs) > 0)

        # Find the valkey.conf config reference
        valkey_conf_ref = None
        for config_ref in service_configs:
            if (
                isinstance(config_ref, dict)
                and config_ref.get("source") == "valkey.conf"
            ):
                valkey_conf_ref = config_ref
                break

        self.assertIsNotNone(valkey_conf_ref)
        valkey_conf_ref = cast(dict, valkey_conf_ref)
        self.assertEqual("/etc/valkey/valkey.conf", valkey_conf_ref["target"])

        # Check that the relative path volume is removed (in favor of the config)
        service_volumes = valkey_service["volumes"]
        self.assertEqual(1, len(service_volumes))
        volume = service_volumes[0]
        self.assertEqual("valkey-data:/data", volume)
