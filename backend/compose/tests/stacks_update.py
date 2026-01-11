from django.urls import reverse
from rest_framework import status

from zane_api.models import Environment
from ..models import ComposeStack, ComposeStackChange, ComposeStackEnvOverride
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
)
from typing import cast
from zane_api.utils import jprint

from .stacks import ComposeStackAPITestBase


class ComposeStackRequestUpdateViewTests(ComposeStackAPITestBase):
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
