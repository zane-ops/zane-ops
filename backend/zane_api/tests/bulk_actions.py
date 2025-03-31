# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status


class BulkDeployServiceViewTests(AuthAPITestCase):
    async def test_bulk_deploy_multiple_services(self):
        await self.acreate_and_deploy_redis_docker_service()
        p, _ = await self.acreate_and_deploy_git_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.bulk_deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                },
            ),
            data={
                "service_ids": [service.id async for service in p.services.all()],
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

        async for service in p.services.all():
            self.assertEqual(2, await service.deployments.acount())

            latest_deployment = await service.deployments.alatest("queued_at")

            self.assertTrue(latest_deployment.is_current_production)
            self.assertIsNotNone(
                self.fake_docker_client.get_deployment_service(latest_deployment)
            )
