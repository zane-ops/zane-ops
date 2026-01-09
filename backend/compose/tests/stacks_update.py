from django.urls import reverse
import os
import responses
from rest_framework import status
from unittest.mock import patch

from zane_api.models import Environment
from zane_api.tests.base import FakeDockerClient
from ..models import (
    ComposeStack,
    ComposeStackChange,
    ComposeStackDeployment,
    ComposeStackEnvOverride,
)
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_MULTIPLE_ROUTES,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
)
from typing import cast
from zane_api.utils import jprint
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


from .stacks import ComposeStackAPITestBase


class ComposeStackRequestUpdateViewTests(ComposeStackAPITestBase):
    def test_update_content_request_create_change(self):
        project = self.create_project()

        # Create and deploy a stack first
        create_stack_payload = {
            "slug": "update-stack",
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
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="update-stack").first()
        )
        self.assertIsNotNone(stack)

        # Deploy the stack to apply initial changes
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

        # Verify no unapplied changes after deployment
        stack.refresh_from_db()
        self.assertEqual(0, stack.unapplied_changes.count())

        # Request content update with new compose file
        update_payload = {
            "user_content": DOCKER_COMPOSE_SIMPLE_DB,
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
        self.assertEqual(
            DOCKER_COMPOSE_SIMPLE_DB.strip(), new_value.get("user_content")
        )
        self.assertIsNotNone(new_value.get("computed_content"))
