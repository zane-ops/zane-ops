from typing import cast

import requests
from zane_api.tests.base import AuthAPITestCase, FakeDockerClient

import responses
from django.urls import reverse
from zane_api.utils import jprint
from rest_framework import status
from ..models import SharedRegistryCredentials, BuildRegistry
from zane_api.models import Deployment

from django.conf import settings
from django.test import override_settings
from temporal.helpers import ZaneProxyClient


@override_settings(IGNORE_GLOBAL_REGISTRY_CHECK=False)
class TestCreateBuildRegistryViewTests(AuthAPITestCase):
    def test_cannot_create_unmanaged_registry_without_external_credentials(self):
        self.loginUser()

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
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

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            username="user",
            password="password",
        )

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
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

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            username="user",
            password="password",
            registry_type=SharedRegistryCredentials.RegistryType.DOCKER_HUB,
        )

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_global_registry_to_prevent_duplicates(self):
        self.loginUser()

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            username="user",
            password="password",
            registry_type=SharedRegistryCredentials.RegistryType.GENERIC,
        )

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        body = {
            "name": "My New registry",
            "is_managed": False,
            "is_global": True,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        registry_one = BuildRegistry.objects.get(name="My registry")
        registry_two = BuildRegistry.objects.get(name="My New registry")
        self.assertFalse(registry_one.is_global)
        self.assertTrue(registry_two.is_global)

    def test_create_global_registry_at_least_one_global_is_required(self):
        self.loginUser()

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            username="user",
            password="password",
            registry_type=SharedRegistryCredentials.RegistryType.GENERIC,
        )

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": False,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, field="is_global"))

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

        registry_credentials = await SharedRegistryCredentials.objects.acreate(
            slug="local",
            url="http://registry.example.com",
            registry_type=SharedRegistryCredentials.RegistryType.DOCKER_HUB,
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

    async def test_create_simple_managed_registry(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        body = {
            "name": "My registry",
            "is_managed": True,
            "is_global": True,
            "url": "http://registry.127.0.0.0.1.sslip.io",
            "username": "fredkisss",
        }
        response = await self.async_client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        registry = cast(
            BuildRegistry,
            await BuildRegistry.objects.select_related("external_credentials").afirst(),
        )
        self.assertIsNotNone(registry)
        self.assertTrue(registry.is_managed)

        # check that it has created credentials
        self.assertIsNotNone(registry.external_credentials)
        credentials = cast(SharedRegistryCredentials, registry.external_credentials)
        self.assertEqual("http://registry.127.0.0.0.1.sslip.io", credentials.url)
        self.assertEqual("fredkisss", credentials.username)

        swarm_service = cast(
            FakeDockerClient.FakeService,
            self.fake_docker_client.service_map.get(registry.swarm_service_name),
        )
        self.assertIsNotNone(swarm_service)
        self.assertGreater(len(swarm_service.attached_volumes), 0)
        self.assertGreater(len(swarm_service.configs), 0)

        # check that it has been added to caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_build_registry(
                registry.service_alias, "registry.127.0.0.0.1.sslip.io"
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_create_new_registry_with_global_unset_the_current_global_registry(self):
        self.loginUser()

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        )

        old_registry = BuildRegistry.objects.create(
            name="global",
            is_managed=False,
            external_credentials=registry_credentials,
        )

        body = {
            "name": "New global",
            "is_managed": False,
            "is_global": True,
            "external_credentials_id": registry_credentials.id,
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_registry = cast(
            BuildRegistry, BuildRegistry.objects.filter(name="New global").first()
        )
        self.assertIsNotNone(new_registry)

        old_registry.refresh_from_db()
        self.assertTrue(new_registry.is_global)
        self.assertFalse(old_registry.is_global)

    def test_delete_registry_cannot_delete_global_registry(self):
        self.loginUser()

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        )

        registry = BuildRegistry.objects.create(
            name="global",
            is_managed=False,
            external_credentials=registry_credentials,
        )

        # Delete registry
        response = self.client.delete(
            reverse(
                "container_registry:build_registries.details",
                kwargs={"id": registry.id},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_credential_with_build_registry_can_only_be_updated_from_build_registry(
        self,
    ):
        self.assertFalse(True)

    def test_update_managed_registry_simple(self):
        self.assertFalse(True)

    def test_update_managed_registry_with_credentials(self):
        self.assertFalse(True)

    async def test_delete_managed_registry_and_associated_service(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        body = {
            "name": "My registry",
            "is_managed": True,
            "is_global": True,
            "url": "http://registry.127.0.0.0.1.sslip.io",
        }
        response = await self.async_client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        registry = cast(
            BuildRegistry,
            await BuildRegistry.objects.select_related("external_credentials").afirst(),
        )
        self.assertIsNotNone(registry)
        self.assertTrue(registry.is_managed)

        credentials = cast(SharedRegistryCredentials, registry.external_credentials)

        # remove global status to prevent conflict error
        registry.is_global = False
        await registry.asave()

        # Delete registry
        response = await self.async_client.delete(
            reverse(
                "container_registry:build_registries.details",
                kwargs={"id": registry.id},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNone(await BuildRegistry.objects.afirst())

        self.assertIsNone(
            await SharedRegistryCredentials.objects.filter(pk=credentials.id).afirst()
        )

        swarm_service = cast(
            FakeDockerClient.FakeService,
            self.fake_docker_client.service_map.get(registry.swarm_service_name),
        )
        self.assertIsNone(swarm_service)

        # check that it has been added to caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_build_registry(
                registry.service_alias, "registry.127.0.0.0.1.sslip.io"
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_delete_unmanaged_registry_does_not_delete_credentials(self):
        self.loginUser()

        registry_credentials = SharedRegistryCredentials.objects.create(
            slug="local",
            url="http://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        )

        registry = BuildRegistry.objects.create(
            name="not global",
            is_managed=False,
            is_global=False,
            external_credentials=registry_credentials,
        )

        # Delete registry
        response = self.client.delete(
            reverse(
                "container_registry:build_registries.details",
                kwargs={"id": registry.id},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNotNone(
            SharedRegistryCredentials.objects.filter(pk=registry_credentials.id).first()
        )
