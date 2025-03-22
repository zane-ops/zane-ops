from django.conf import settings

from .base import AuthAPITestCase


from ..models import Deployment, ServiceMetrics
from django.urls import reverse
from rest_framework import status
from ..temporal import (
    GetDockerDeploymentStatsWorkflow,
    SimpleDeploymentDetails,
)


class DockerServiceMetricsScheduleTests(AuthAPITestCase):
    async def test_create_metrics_schedule_when_deploying_a_service(self):
        _, service = await self.acreate_and_deploy_redis_docker_service()

        initial_deployment: Deployment = (
            await service.alatest_production_deployment
        )  # type: ignore

        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(
            self.get_workflow_schedule_by_id(initial_deployment.metrics_schedule_id)
        )

    async def test_delete_previous_deployment_metrics_schedule_on_new_deployment(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: Deployment = (
            await service.alatest_production_deployment
        )  # type: ignore

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertIsNone(
            self.get_workflow_schedule_by_id(initial_deployment.metrics_schedule_id)
        )

    async def test_run_stats_schedule(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: Deployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                Deployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            deployment = SimpleDeploymentDetails(
                hash=latest_deployment.hash,
                service_id=latest_deployment.service.id,
                project_id=latest_deployment.service.project_id,
            )
            await env.client.execute_workflow(
                workflow=GetDockerDeploymentStatsWorkflow.run,
                arg=deployment,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            metrics_count = await ServiceMetrics.objects.filter(
                deployment__hash=deployment.hash, service=service
            ).acount()
            self.assertGreater(metrics_count, 0)
