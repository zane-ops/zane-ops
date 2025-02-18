from django.conf import settings

from .base import AuthAPITestCase


from ..models import DockerDeployment, ServiceMetrics
from django.urls import reverse
from rest_framework import status
from ..temporal import (
    GetDockerDeploymentStatsWorkflow,
    SimpleDeploymentDetails,
)
from ..utils import jprint, convert_value_to_bytes


class DockerServiceMetricsScheduleTests(AuthAPITestCase):
    async def test_create_metrics_schedule_when_deploying_a_service(self):
        _, service = await self.acreate_and_deploy_redis_docker_service()

        initial_deployment: DockerDeployment = (
            await service.alatest_production_deployment
        )  # type: ignore

        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(
            self.get_workflow_schedule_by_id(initial_deployment.metrics_schedule_id)
        )

    async def test_delete_previous_deployment_metrics_schedule_on_new_deployment(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: DockerDeployment = (
            await service.alatest_production_deployment
        )  # type: ignore

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertIsNone(
            self.get_workflow_schedule_by_id(initial_deployment.metrics_schedule_id)
        )

    async def test_run_stats_schedule(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: DockerDeployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
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


class DockerServiceMetricsViewTests(AuthAPITestCase):
    async def test_get_service_metrics(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: (
            DockerDeployment
        ) = await service.alatest_production_deployment  # type: ignore

        await ServiceMetrics.objects.abulk_create(
            [
                ServiceMetrics(
                    cpu_percent=4.98,
                    memory_bytes=convert_value_to_bytes(250, "KILOBYTES"),
                    net_tx_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    net_rx_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    disk_read_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    disk_writes_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    deployment=initial_deployment,
                    service=service,
                ),
                ServiceMetrics(
                    cpu_percent=6.12,
                    memory_bytes=convert_value_to_bytes(1.6, "MEGABYTES"),
                    net_tx_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    net_rx_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    disk_read_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    disk_writes_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    deployment=initial_deployment,
                    service=service,
                ),
                ServiceMetrics(
                    cpu_percent=3.56,
                    memory_bytes=convert_value_to_bytes(5895, "KILOBYTES"),
                    net_tx_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    net_rx_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    disk_read_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    disk_writes_bytes=convert_value_to_bytes(45, "KILOBYTES"),
                    deployment=initial_deployment,
                    service=service,
                ),
            ]
        )

        response = await self.async_client.get(
            reverse(
                "zane_api:services.docker.metrics",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        jprint(response.json())
        self.assertEqual(3, len(response.json()))
