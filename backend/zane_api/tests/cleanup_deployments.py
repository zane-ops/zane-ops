import asyncio
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import Deployment, Environment
from django.conf import settings
from temporal.workflows import (
    DeployDockerServiceWorkflow,
    DockerDeploymentStep,
)
from ..utils import jprint


from temporalio.common import RetryPolicy


class CleanupDeploymentViewTests(AuthAPITestCase):
    async def test_cleanup_non_active_queue(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                project, service = await self.acreate_redis_docker_service()
                # ========================
                #  Deployment to cancel  #
                # ========================
                # stop it so that it has the time to receive the signal if sent
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

                # simulate two new deployment issued after the first
                await self.prepare_new_deployment(service)
                await self.prepare_new_deployment(service)

                response = await self.async_client.put(
                    reverse(
                        "zane_api:services.cleanup_deployment_queue",
                        kwargs={
                            "project_slug": project.slug,
                            "service_slug": service.slug,
                            "env_slug": Environment.PRODUCTION_ENV,
                        },
                    ),
                )
                # run active deployment
                await workflow_result_task

                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

                deployment_count = await service.deployments.acount()
                self.assertEqual(3, deployment_count)

                cancelled_deployments = await Deployment.objects.filter(
                    status=Deployment.DeploymentStatus.CANCELLED
                ).acount()
                self.assertEqual(2, cancelled_deployments)

                earliest_deployment = await service.deployments.aearliest("queued_at")
                self.assertEqual(
                    Deployment.DeploymentStatus.HEALTHY,
                    earliest_deployment.status,
                )

    async def test_cleanup_full_queue(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                project, service = await self.acreate_redis_docker_service()
                # ========================
                #  Deployment to cancel  #
                # ========================
                # stop it so that it has the time to receive the signal if sent
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

                # simulate two new deployment issued after the first
                await self.prepare_new_deployment(service)
                await self.prepare_new_deployment(service)

                deployment_count = await service.deployments.acount()
                self.assertEqual(3, deployment_count)
                [_, response] = await asyncio.gather(
                    workflow_result_task,
                    self.async_client.put(
                        reverse(
                            "zane_api:services.cleanup_deployment_queue",
                            kwargs={
                                "project_slug": project.slug,
                                "service_slug": service.slug,
                                "env_slug": Environment.PRODUCTION_ENV,
                            },
                        ),
                        data={"cancel_running_deployments": True},
                    ),
                )
                # run active deployment
                # await workflow_result_task

                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

                deployment_count = await service.deployments.acount()
                self.assertEqual(3, deployment_count)

                cancelled_deployments = await Deployment.objects.filter(
                    status=Deployment.DeploymentStatus.CANCELLED
                ).acount()
                self.assertEqual(3, cancelled_deployments)


class CleanupDeploymentPreserveLatestViewTests(AuthAPITestCase):
    async def test_cleanup_queue_on_new_deploy(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                project, service = await self.acreate_redis_docker_service()
                # ========================
                #  Deployments to cancel  #
                # ========================
                # stop it so that it has the time to receive the signal if sent
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

                # simulate two new deployment issued after the first
                await self.prepare_new_deployment(service)
                await self.prepare_new_deployment(service)

                response = await self.async_client.put(
                    reverse(
                        "zane_api:services.docker.deploy_service",
                        kwargs={
                            "project_slug": project.slug,
                            "service_slug": service.slug,
                            "env_slug": Environment.PRODUCTION_ENV,
                        },
                    ),
                    data={"cleanup_queue": True},
                )
                # run active deployment
                await workflow_result_task

                self.assertEqual(response.status_code, status.HTTP_200_OK)

                deployment_count = await service.deployments.acount()
                self.assertEqual(4, deployment_count)

                cancelled_deployments = await Deployment.objects.filter(
                    status=Deployment.DeploymentStatus.CANCELLED
                ).acount()
                self.assertEqual(3, cancelled_deployments)

                earliest_deployment = await service.deployments.alatest("queued_at")
                self.assertEqual(
                    Deployment.DeploymentStatus.HEALTHY,
                    earliest_deployment.status,
                )
