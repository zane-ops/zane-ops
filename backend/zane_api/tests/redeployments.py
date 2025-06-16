import asyncio
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import Deployment, Environment
from django.conf import settings
from temporal.workflows import (
    DeployDockerServiceWorkflow,
    DeployGitServiceWorkflow,
    DockerDeploymentStep,
)


from temporalio.common import RetryPolicy


class ServicesDeployWithCancel(AuthAPITestCase):
    async def test_deploy_docker_service_accept_cancelling_previous(self):
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
                    data={"cleanup_deployment_queue": True},
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

    async def test_deploy_git_service_accept_cancelling_previous(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                project, service = await self.acreate_and_deploy_git_service()
                # ========================
                #  Deployment to cancel  #
                # ========================
                # ignore the first one
                await self.prepare_new_deployment(service)
                payload = await self.prepare_new_deployment(
                    service, pause_at_step=DockerDeploymentStep.INITIALIZED
                )
                workflow_handle = await env.client.start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                response = await self.async_client.put(
                    reverse(
                        "zane_api:services.git.deploy_service",
                        kwargs={
                            "project_slug": project.slug,
                            "service_slug": service.slug,
                            "env_slug": Environment.PRODUCTION_ENV,
                        },
                    ),
                    data={"cleanup_deployment_queue": True},
                )
                # finish background task
                await workflow_result_task

                self.assertEqual(response.status_code, status.HTTP_200_OK)

                deployment_count = await service.deployments.acount()
                self.assertEqual(4, deployment_count)

                cancelled_deployments = await Deployment.objects.filter(
                    status=Deployment.DeploymentStatus.CANCELLED
                ).acount()
                self.assertEqual(2, cancelled_deployments)

                latest_deployment = await service.deployments.alatest("queued_at")
                self.assertEqual(
                    Deployment.DeploymentStatus.HEALTHY,
                    latest_deployment.status,
                )


class ServicesWebhookDeployWithCancel(AuthAPITestCase):
    async def test_webhook_deploy_docker_service_accept_cancelling_previous(self):
        async with self.workflowEnvironment() as env:
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
                    "zane_api:services.docker.webhook_deploy",
                    kwargs={"deploy_token": service.deploy_token},
                ),
                data={"cleanup_deployment_queue": True},
            )
            # finish background task
            await workflow_result_task

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

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

    async def test_webhook_deploy_git_service_accept_cancelling_previous(self):
        async with self.workflowEnvironment() as env:
            _, service = await self.acreate_and_deploy_git_service()
            # ========================
            #  Deployment to cancel  #
            # ========================
            # ignore the first one
            await self.prepare_new_deployment(service)
            payload = await self.prepare_new_deployment(
                service, pause_at_step=DockerDeploymentStep.INITIALIZED
            )
            workflow_handle = await env.client.start_workflow(
                workflow=DeployGitServiceWorkflow.run,
                arg=payload,
                id=payload.workflow_id,
                retry_policy=RetryPolicy(maximum_attempts=1),
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            workflow_result_task = asyncio.create_task(workflow_handle.result())

            response = await self.async_client.put(
                reverse(
                    "zane_api:services.git.webhook_deploy",
                    kwargs={"deploy_token": service.deploy_token},
                ),
                data={"cleanup_deployment_queue": True},
            )
            # finish background task
            await workflow_result_task

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

            deployment_count = await service.deployments.acount()
            self.assertEqual(4, deployment_count)

            cancelled_deployments = await Deployment.objects.filter(
                status=Deployment.DeploymentStatus.CANCELLED
            ).acount()
            self.assertEqual(2, cancelled_deployments)

            latest_deployment = await service.deployments.alatest("queued_at")
            self.assertEqual(
                Deployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )
