from typing import cast
from zane_api.tests.base import AuthAPITestCase

import responses
from django.urls import reverse
from zane_api.utils import jprint
from rest_framework import status
from ..models import ContainerRegistryCredentials, BuildRegistry
from zane_api.models import DeploymentChange, Project, Service, Deployment

from django.conf import settings
from django.test import override_settings


@override_settings(IGNORE_GLOBAL_REGISTRY_CHECK=False)
class TestCreateBuildRegistryViewTests(AuthAPITestCase):
    def test_cannot_create_unmanaged_registry_without_external_credentials(self):
        self.loginUser()

        body = {
            "name": "My registry",
            "is_managed": False,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "external_credentials_id")
        )

    def test_create_simple_unmanaged_registry(self):
        self.loginUser()

        registry_credentials = ContainerRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            username="user",
            password="password",
        )

        body = {
            "name": "My registry",
            "is_managed": False,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_registry = cast(BuildRegistry, BuildRegistry.objects.first())
        self.assertIsNotNone(created_registry)

    def test_unmanaged_registry_only_accept_generic_credentials(self):
        self.loginUser()

        registry_credentials = ContainerRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            username="user",
            password="password",
            registry_type=ContainerRegistryCredentials.RegistryType.DOCKER_HUB,
        )

        body = {
            "name": "My registry",
            "is_managed": False,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate()
    async def test_build_git_service_fails_if_no_global_registry(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        p, service = await self.acreate_git_service(
            repository_url="https://gitlab.com/fredkiss3/private-ac",
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        first_deployment = cast(Deployment, await service.deployments.afirst())
        self.assertIsNotNone(first_deployment)
        self.assertEqual(Deployment.DeploymentStatus.FAILED, first_deployment.status)

    @responses.activate()
    async def test_build_git_service_push_to_global_registry(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        registry_credentials = await ContainerRegistryCredentials.objects.acreate(
            slug="local",
            url="http://registry.example.com",
            registry_type=ContainerRegistryCredentials.RegistryType.DOCKER_HUB,
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        )

        registry = await BuildRegistry.objects.acreate(
            name="global",
            is_managed=False,
            external_credentials=registry_credentials,
        )

        p, service = await self.acreate_git_service(
            repository_url="https://gitlab.com/fredkiss3/private-ac",
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        first_deployment = cast(Deployment, await service.deployments.afirst())
        self.assertIsNotNone(first_deployment)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, first_deployment.status)
        image_name = registry.registry_url + "/" + first_deployment.image_tag

        # image pushed to registry
        self.assertTrue(image_name in self.fake_docker_client.image_registry)
