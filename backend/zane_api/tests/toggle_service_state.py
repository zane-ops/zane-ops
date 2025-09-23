# type: ignore
from unittest.mock import MagicMock
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import (
    Deployment,
)
from temporal.activities import (
    get_swarm_service_name_for_deployment,
)


class DockerToggleServiceViewTests(AuthAPITestCase):
    async def test_stop_service(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data={"desired_state": "stop"},
        )

        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        first_deployment: Deployment = await service.deployments.afirst()
        self.assertIsNotNone(first_deployment)
        self.assertEqual(Deployment.DeploymentStatus.SLEEPING, first_deployment.status)
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.update.assert_called()
        scaled_up = any(
            call.kwargs.get("mode") == {"Replicated": {"Replicas": 0}}
            for call in fake_service.update.call_args_list
        )
        self.assertTrue(scaled_up)
        monitor_schedule = self.get_workflow_schedule_by_id(
            first_deployment.monitor_schedule_id
        )
        self.assertFalse(monitor_schedule.is_running)

    async def test_restart_service(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],  # stopped
            [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "Spec": {
                        "ContainerSpec": {"Image": "ghcr.io/zane-ops/zane-ops:v1.11.1"}
                    },
                    "DesiredState": "running",
                }
            ],  # restarted
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data={"desired_state": "stop"},
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data={"desired_state": "start"},
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

        first_deployment: Deployment = await service.deployments.afirst()

        self.assertEqual(Deployment.DeploymentStatus.STARTING, first_deployment.status)
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.update.assert_called()
        scaled_up = any(
            call.kwargs.get("mode") == {"Replicated": {"Replicas": 1}}
            for call in fake_service.update.call_args_list
        )
        self.assertTrue(scaled_up)
        monitor_schedule = self.get_workflow_schedule_by_id(
            first_deployment.monitor_schedule_id
        )
        self.assertTrue(monitor_schedule.is_running)

    async def test_cannot_stop_service_if_not_deployed_yet(self):
        project, service = await self.acreate_redis_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data={"desired_state": "stop"},
        )

        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    async def test_bulk_toggle_services(self):
        await self.acreate_and_deploy_redis_docker_service()
        project, _ = await self.acreate_and_deploy_caddy_docker_service()
        fake_service = MagicMock()
        fake_service.tasks.side_effect = lambda *args, **kwargs: []
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        response = await self.async_client.put(
            reverse(
                "zane_api:services.bulk_toggle_state",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data={
                "desired_state": "stop",
                "service_ids": [service.id async for service in project.services.all()],
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        async for service in project.services.all():

            first_deployment: Deployment = await service.deployments.afirst()
            self.assertIsNotNone(first_deployment)
            self.assertEqual(
                Deployment.DeploymentStatus.SLEEPING, first_deployment.status
            )
            monitor_schedule = self.get_workflow_schedule_by_id(
                first_deployment.monitor_schedule_id
            )
            self.assertFalse(monitor_schedule.is_running)
