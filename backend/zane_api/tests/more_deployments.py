from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    DockerDeploymentChange,
)
from ..utils import jprint


class DockerServiceWebhookDeployViewTests(AuthAPITestCase):
    def test_generate_deploy_token_for_service(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        response = self.client.patch(
            reverse(
                "zane_api:services.docker.regenerate_deploy_token",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        self.assertIsNotNone(service.deploy_token)
        self.assertEqual(20, len(service.deploy_token))

    def test_generate_deploy_token_for_service_on_creation(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = DockerRegistryService.objects.get(slug="cache-db")
        self.assertIsNotNone(created_service.deploy_token)
        self.assertEqual(20, len(created_service.deploy_token))

    async def test_webhook_deploy_service(self):
        _, service = await self.acreate_and_deploy_caddy_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

    async def test_webhook_deploy_service_unauthenticated(self):
        _, service = await self.acreate_and_deploy_caddy_docker_service()
        await self.async_client.alogout()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

    async def test_webhook_deploy_service_with_image_and_commit_message(self):
        _, service = await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "new_image": "valkey/valkey:7.3-alpine",
                "commit_message": "Upgrade valkey image",
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service = await DockerRegistryService.objects.aget(slug=service.slug)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

        self.assertEqual("Upgrade valkey image", new_deployment.commit_message)
        self.assertEqual("valkey/valkey:7.3-alpine", service.image)


class DockerServiceRequestChangesViewTests(AuthAPITestCase):
    async def test_validate_conflicting_changes_for_single_field_types_should_merge(
        self,
    ):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "cpus": 1,
            },
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {"cpus": 2, "memory": {"value": 500}},
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        service = await DockerRegistryService.objects.aget(slug=service.slug)
        unapplied_changes_count = await DockerDeploymentChange.objects.filter(
            service__slug=service.slug, applied=False
        ).acount()

        self.assertEqual(1, unapplied_changes_count)

        resource_limit_change: DockerDeploymentChange = (
            await DockerDeploymentChange.objects.filter(
                applied=False,
                field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            ).afirst()
        )
        self.assertEqual(
            {"cpus": 2, "memory": {"value": 500, "unit": "MEGABYTES"}},
            resource_limit_change.new_value,
        )
