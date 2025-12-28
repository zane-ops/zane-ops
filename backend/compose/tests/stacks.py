from django.urls import reverse
from rest_framework import status

from zane_api.models import Project, Environment
from zane_api.tests.base import AuthAPITestCase
from ..models import ComposeStack, ComposeStackChange
from .fixtures import DOCKER_COMPOSE_MINIMAL
from typing import cast
from zane_api.utils import jprint
import yaml


class ComposeStackAPITestCase(AuthAPITestCase):
    """Base test class for compose stack tests with helper methods"""

    def create_project(self, slug="my-project"):
        """Helper to create a project and return it"""
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


class CreateComposeStackViewTests(ComposeStackAPITestCase):
    def test_create_simple_compose_stack(self):
        """Test creating a stack with minimal valid compose file"""
        project = self.create_project()

        # Create compose stack
        create_stack_payload = {
            "slug": "my-stack",
            "compose_content": DOCKER_COMPOSE_MINIMAL,
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
        self.assertEqual(created_stack.user_compose_content, DOCKER_COMPOSE_MINIMAL)
        self.assertIsNotNone(created_stack.computed_compose_spec)

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
        self.assertIsNotNone(new_value.get("user_compose_content"))
        self.assertIsNotNone(new_value.get("computed_compose_spec"))
        print(
            yaml.safe_dump(
                new_value.get("computed_compose_spec"),
                default_flow_style=False,
                sort_keys=False,
            )
        )
