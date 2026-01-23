"""
Tests for double underscore prefix convention in x-zane-env variables.

Double underscore-prefixed variables (e.g., __DB_NAME) are marked as exposed
and automatically create env overrides. The key keeps its double underscore prefix.
"""

from django.urls import reverse

from zane_api.models import Environment

from ..models import ComposeStackChange
from ..processor import ComposeSpecProcessor
from .fixtures import (
    DOCKER_COMPOSE_WITH_MIXED_ENV_TYPES,
    DOCKER_COMPOSE_WITH_PREFIXED_ENV_EXPANSION,
    DOCKER_COMPOSE_WITH_PREFIXED_ENV_OVERRIDE,
    DOCKER_COMPOSE_WITH_PREFIXED_SIMPLE,
)
from .stacks import ComposeStackAPITestBase
from zane_api.utils import jprint
from rest_framework import status


class ProcessorEnvPrefixTests(ComposeStackAPITestBase):
    def test_prefixed_vars_are_exposed(self):
        """
        Prefixed vars (__KEY) have is_exposed=True, plain vars have is_exposed=False.
        Keys retain their double underscore prefix.
        """
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_PREFIXED_ENV_OVERRIDE
        )
        stack.env_overrides.all().delete()

        spec = ComposeSpecProcessor.process_compose_spec(
            user_content=DOCKER_COMPOSE_WITH_PREFIXED_ENV_OVERRIDE,
            stack=stack,
        )

        # Prefixed vars keep double underscore, is_exposed=True
        self.assertIn("__DATABASE_PASSWORD", spec.envs)
        self.assertIn("__API_KEY", spec.envs)
        self.assertTrue(spec.envs["__DATABASE_PASSWORD"].is_exposed)
        self.assertTrue(spec.envs["__API_KEY"].is_exposed)

        # Non-prefixed: is_exposed=False
        self.assertIn("REGULAR_VAR", spec.envs)
        self.assertFalse(spec.envs["REGULAR_VAR"].is_exposed)

    def test_override_creation_for_exposed_vars(self):
        """
        Prefixed and template vars create overrides, plain vars don't.
        """
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_MIXED_ENV_TYPES
        )

        override_keys = set(stack.env_overrides.values_list("key", flat=True))

        # Template + prefixed create overrides (prefixed keep double underscore)
        self.assertIn("DB_PASSWORD", override_keys)
        self.assertIn("__DB_NAME", override_keys)
        self.assertIn("__API_SECRET", override_keys)

        # Plain vars don't
        self.assertNotIn("DB_USER", override_keys)
        self.assertNotIn("API_URL", override_keys)

    def test_variable_expansion(self):
        """${__DATABASE_URL} resolves correctly."""
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_PREFIXED_ENV_EXPANSION
        )

        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=DOCKER_COMPOSE_WITH_PREFIXED_ENV_EXPANSION,
            stack=stack,
        )

        x_env = artifacts.computed_spec.get("x-zane-env", {})
        self.assertEqual("postgres://user@localhost:5432/mydb", x_env["__DATABASE_URL"])

    def test_override_recreated_after_deletion(self):
        """Deleted override recreated on next deploy."""
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WITH_PREFIXED_SIMPLE
        )

        # Delete override
        override = stack.env_overrides.get(key="__CONFIG_VALUE")
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
                "field": ComposeStackChange.ChangeField.ENV_OVERRIDES,
                "type": ComposeStackChange.ChangeType.DELETE,
                "item_id": override.id,
            },
        )
        jprint(response.json())
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        stack.refresh_from_db()
        self.assertTrue(stack.env_overrides.filter(key="__CONFIG_VALUE").exists())
