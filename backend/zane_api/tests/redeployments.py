from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import Deployment, Environment
from asgiref.sync import sync_to_async
from ..serializers import ServiceSerializer
from django.conf import settings
from temporal.shared import (
    DeploymentDetails,
    DeployServiceWorkflowResult,
)
from temporal.workflows import DeployDockerServiceWorkflow, DockerDeploymentStep
import asyncio
from temporalio.common import RetryPolicy


class DockerServiceDeployWithCancel(AuthAPITestCase):
    async def test_deploy_service_accept_cancelling_previous(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                p, service = await self.acreate_and_deploy_redis_docker_service()

                # ========================
                #   Initial deployment   #
                # ========================
                payload = await self.prepare_new_deployment(
                    service, pause_at_step=DockerDeploymentStep.INITIALIZED
                )
                workflow_handle_first = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )
                workflow_result_task_first = asyncio.create_task(
                    workflow_handle_first.result()
                )

                # ========================
                #    Second deployment   #
                # ========================
                payload2 = await self.prepare_new_deployment(
                    service,
                )

                print(f"{payload.workflow_id=} {payload2.workflow_id=}")

                workflow_handle_second = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload2,
                    id=payload2.workflow_id,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )
                workflow_result_task_second = asyncio.create_task(
                    workflow_handle_second.result()
                )

                print("waiting for both tasks to finish...")
                [workflow_result_first, workflow_result_second] = await asyncio.gather(
                    workflow_result_task_first, workflow_result_task_second
                )
                print("Both tasks finished !")

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result_first.deployment_status,
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.HEALTHY,
                    workflow_result_second.deployment_status,
                )

                deployment_count = await service.deployments.acount()
                self.assertEqual(2, deployment_count)

                # await new_deployment.arefresh_from_db()
                # self.assertEqual(
                #     Deployment.DeploymentStatus.CANCELLED, new_deployment.status
                # )
                latest_deployment = await service.deployments.alatest("queued_at")
                self.assertNotEqual(
                    Deployment.DeploymentStatus.CANCELLED, latest_deployment.status
                )
