import asyncio
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import Deployment, Environment
from django.conf import settings
from temporal.workflows import DeployDockerServiceWorkflow, DockerDeploymentStep
from django.db.models import Q

from temporalio.common import RetryPolicy


class DockerServiceDeployWithCancel(AuthAPITestCase):
    async def test_deploy_service_accept_cancelling_previous(self):  # Added mock args
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                project, service = await self.acreate_redis_docker_service()
                # ========================
                #  Deployment to cancel  #
                # ========================
                # ignore the first one
                await self.prepare_new_deployment(service)
                payload = await self.prepare_new_deployment(
                    service, pause_at_step=DockerDeploymentStep.INITIALIZED
                )
                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                response = await self.async_client.put(
                    reverse(
                        "zane_api:services.docker.deploy_service",
                        kwargs={
                            "project_slug": project.slug,
                            "service_slug": service.slug,
                            "env_slug": Environment.PRODUCTION_ENV,
                        },
                    ),
                    data={"cancel_previous": True},
                    format="json",
                )
                # finish background task
                await workflow_result_task

                self.assertEqual(response.status_code, status.HTTP_200_OK)

                deployment_count = await service.deployments.acount()
                self.assertEqual(3, deployment_count)

                cancelled_deployments = await Deployment.objects.filter(
                    status=Deployment.DeploymentStatus.CANCELLED
                ).acount()
                self.assertEqual(2, cancelled_deployments)

                latest_deployment = await service.deployments.alatest("queued_at")
                self.assertEqual(
                    Deployment.DeploymentStatus.HEALTHY,
                    latest_deployment.status,
                )
