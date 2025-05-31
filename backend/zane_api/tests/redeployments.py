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
from temporal.workflows import DeployDockerServiceWorkflow
import asyncio
from temporalio.common import RetryPolicy


class DockerServiceDeployWithCancel(AuthAPITestCase):
    async def test_deploy_service_accept_cancelling_previous(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                p, service = await self.acreate_and_deploy_redis_docker_service()
                service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                new_deployment: Deployment = await Deployment.objects.acreate(
                    service_snapshot=service_snapshot,
                    service=service,
                )

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    # pause_at_step=DockerDeploymentStep.INITIALIZED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # launch new deployment concurrently
                response = await self.async_client.put(
                    reverse(
                        "zane_api:services.docker.deploy_service",
                        kwargs={
                            "project_slug": p.slug,
                            "env_slug": Environment.PRODUCTION_ENV,
                            "service_slug": service.slug,
                        },
                    ),
                    data={"cancel_previous": True},
                )
                self.assertEqual(status.HTTP_200_OK, response.status_code)

                # # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                # deployment_count = await service.deployments.acount()
                # self.assertEqual(2, deployment_count)

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                # self.assertIsNone(workflow_result.healthcheck_result)
                # await new_deployment.arefresh_from_db()
                # self.assertEqual(
                #     Deployment.DeploymentStatus.CANCELLED, new_deployment.status
                # )
                latest_deployment = await service.deployments.alatest("queued_at")
                self.assertNotEqual(
                    Deployment.DeploymentStatus.CANCELLED, latest_deployment.status
                )
