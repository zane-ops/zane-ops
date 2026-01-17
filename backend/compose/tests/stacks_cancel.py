from django.urls import reverse
from rest_framework import status
from django.conf import settings
import asyncio
from datetime import timedelta
from temporalio.common import RetryPolicy

from zane_api.models import Environment
from ..models import (
    ComposeStack,
    ComposeStackChange,
    ComposeStackDeployment,
)
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
)
from typing import cast
from zane_api.utils import jprint
from temporal.workflows import DeployComposeStackWorkflow
from temporal.shared import ComposeStackDeploymentDetails, CancelDeploymentSignalInput

from .stacks import ComposeStackAPITestBase
from compose.views.serializers import ComposeStackSnapshotSerializer
from asgiref.sync import sync_to_async


class ComposeStackCancelViewTests(ComposeStackAPITestBase):
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
        response = await self.async_client.put(
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

    async def test_cancel_running_deployment(self):
        return  # FIXME: we need to remove
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
                await stack.arefresh_from_db()

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
