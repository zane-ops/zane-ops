from django.urls import reverse
from rest_framework import status

from zane_api.models import Project, Environment
from zane_api.tests.base import AuthAPITestCase
from ..models import ComposeStack, ComposeStackChange
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WITH_HOST_VOLUME,
)
from typing import Any, cast
from zane_api.utils import jprint, find_item_in_sequence


class ComposeStackAPITestBase(AuthAPITestCase):
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


class CreateComposeStackViewTests(ComposeStackAPITestBase):
    def test_create_simple_compose_stack(self):
        """Test creating a stack with minimal valid compose file"""
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
        """Test creating a stack with volumes to verify volume reconciliation"""
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

        self.assertNotEqual("db-data", db_volume["source"])
        self.assertTrue(db_volume["source"].endswith("db-data"))
        self.assertEqual("/var/lib/postgresql", db_volume["target"])

    def test_create_compose_stack_with_host_volumes(self):
        """Test creating a stack with host volumes to verify volume reconciliation"""
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
