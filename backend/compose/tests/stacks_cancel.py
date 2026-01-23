from typing import cast
from django.urls import reverse
from rest_framework import status
from django.conf import settings
import asyncio
from datetime import timedelta
from temporalio.common import RetryPolicy

from zane_api.models import Environment
from ..models import (
    ComposeStackChange,
    ComposeStackDeployment,
)
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
)
from zane_api.utils import jprint
from temporal.workflows import DeployComposeStackWorkflow
from temporal.shared import ComposeStackDeploymentDetails, CancelDeploymentSignalInput

from .stacks import ComposeStackAPITestBase
from compose.views.serializers import ComposeStackSnapshotSerializer
from asgiref.sync import sync_to_async


class ComposeStackCancelViewTests(ComposeStackAPITestBase):
    async def test_cancel_running_deployment(self):
        project, stack = await self.acreate_and_deploy_compose_stack(
            DOCKER_COMPOSE_MINIMAL
        )
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                # Create a new deployment
                new_deployment = await ComposeStackDeployment.objects.acreate(
                    stack=stack,
                    commit_message="Update stack",
                )

                # Create a change to trigger redeployment
                await ComposeStackChange.objects.acreate(
                    stack=stack,
                    field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                    type=ComposeStackChange.ChangeType.UPDATE,
                    new_value=DOCKER_COMPOSE_SIMPLE_DB,
                    applied=False,
                )

                # Apply changes to get stack snapshot
                await sync_to_async(stack.apply_pending_changes)(new_deployment)

                def get_data():
                    return ComposeStackSnapshotSerializer(stack).data

                stack_data = await sync_to_async(get_data)()
                new_deployment.stack_snapshot = stack_data  # type: ignore
                await new_deployment.asave()

                payload = ComposeStackDeploymentDetails.from_deployment(new_deployment)

                # Start the workflow
                workflow_handle = await env.client.start_workflow(
                    workflow=DeployComposeStackWorkflow.run,
                    arg=payload,
                    id=new_deployment.workflow_id,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send cancel signal
                await workflow_handle.signal(
                    DeployComposeStackWorkflow.cancel,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for workflow to complete
                await workflow_result_task

                # Verify deployment was cancelled
                await new_deployment.arefresh_from_db()
                self.assertEqual(
                    ComposeStackDeployment.DeploymentStatus.CANCELLED,
                    new_deployment.status,
                )
                self.assertIsNotNone(new_deployment.status_reason)
                self.assertIsNotNone(new_deployment.finished_at)


class ComposeStackCancelEndpointTests(ComposeStackAPITestBase):
    async def test_cancel_queued_deployment_sets_status_to_cancelled(self):
        """Cancelling a queued (not started) deployment should set status directly."""
        project, stack = await self.acreate_and_deploy_compose_stack(
            DOCKER_COMPOSE_MINIMAL
        )

        # Create a new queued deployment
        new_deployment = await ComposeStackDeployment.objects.acreate(
            stack=stack,
            commit_message="Update stack",
        )

        response = await self.async_client.put(
            reverse(
                "compose:stacks.deployments.cancel",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": new_deployment.hash,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await new_deployment.arefresh_from_db()
        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.CANCELLED,
            new_deployment.status,
        )
        self.assertIsNotNone(new_deployment.status_reason)

    async def test_cannot_cancel_already_finished_deployment(self):
        """Cannot cancel a deployment that has already finished."""
        project, stack = await self.acreate_and_deploy_compose_stack(
            DOCKER_COMPOSE_MINIMAL
        )

        # Get the first deployment which is already finished
        first_deployment = cast(
            ComposeStackDeployment, await stack.deployments.afirst()
        )
        self.assertIsNotNone(first_deployment.finished_at)

        response = await self.async_client.put(
            reverse(
                "compose:stacks.deployments.cancel",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": first_deployment.hash,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    async def test_cancel_deployment_not_found(self):
        """Cancelling a non-existent deployment should return 404."""
        project, stack = await self.acreate_and_deploy_compose_stack(
            DOCKER_COMPOSE_MINIMAL
        )

        response = await self.async_client.put(
            reverse(
                "compose:stacks.deployments.cancel",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": "nonexistent_hash",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
