from typing import cast

import requests
from zane_api.tests.base import AuthAPITestCase, FakeDockerClient

import responses
from django.urls import reverse
from zane_api.utils import jprint, find_item_in_sequence
from rest_framework import status
from ..models import SharedRegistryCredentials, BuildRegistry
from zane_api.models import Deployment

from django.conf import settings
from django.test import override_settings
from temporal.helpers import ZaneProxyClient
from temporal.activities.registries import get_config_name_for_registry


@override_settings(IGNORE_GLOBAL_REGISTRY_CHECK=False)
class TestCreateBuildRegistryViewTests(AuthAPITestCase):
    def test_create_simple_unmanaged_registry(self):
        self.loginUser()

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
            "registry_username": "user",
            "registry_password": "password",
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_registry = cast(BuildRegistry, BuildRegistry.objects.first())

        self.assertIsNotNone(new_registry)

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
    async def test_create_simple_managed_registry(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        body = {
            "name": "My registry",
            "is_managed": True,
            "is_global": True,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
            "registry_username": "fredkisss",
        }
        response = await self.async_client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        registry = cast(
            BuildRegistry,
            await BuildRegistry.objects.afirst(),
        )
        self.assertIsNotNone(registry)
        self.assertTrue(registry.is_managed)

        # check that it has created credentials
        self.assertEqual("registry.127.0.0.0.1.sslip.io", registry.registry_domain)
        self.assertEqual("fredkisss", registry.registry_username)
        self.assertGreater(len(registry.registry_password), 0)

        swarm_service = cast(
            FakeDockerClient.FakeService,
            self.fake_docker_client.service_map.get(
                cast(str, registry.swarm_service_name)
            ),
        )
        self.assertIsNotNone(swarm_service)
        self.assertGreater(len(swarm_service.attached_volumes), 0)
        self.assertGreater(len(swarm_service.configs), 0)

        # check that it has been added to caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_build_registry(
                cast(str, registry.service_alias), "registry.127.0.0.0.1.sslip.io"
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
            registry_domain="registry.example.com",
            registry_username="zane",
            registry_password="password",
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

        registry = BuildRegistry.objects.create(
            name="global",
            is_managed=False,
            registry_domain="registry.example.com",
            registry_username="zane",
            registry_password="password",
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

    @responses.activate()
    async def test_delete_managed_registry_and_associated_service(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        body = {
            "name": "My registry",
            "is_managed": True,
            "is_global": True,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
        }
        response = await self.async_client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        registry = cast(
            BuildRegistry,
            await BuildRegistry.objects.afirst(),
        )
        self.assertIsNotNone(registry)
        self.assertTrue(registry.is_managed)

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

        swarm_service = cast(
            FakeDockerClient.FakeService,
            self.fake_docker_client.service_map.get(
                cast(str, registry.swarm_service_name)
            ),
        )
        self.assertIsNone(swarm_service)

        # check that it has been added to caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_build_registry(
                cast(str, registry.service_alias), "registry.127.0.0.0.1.sslip.io"
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

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

        fake_credentials = self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS
        registry = await BuildRegistry.objects.acreate(
            name="global",
            is_managed=True,
            registry_domain="registry.example.com",
            registry_username=fake_credentials["username"],
            registry_password=fake_credentials["password"],
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
        image_name = registry.registry_domain + "/" + first_deployment.image_tag

        # image pushed to registry
        self.assertTrue(image_name in self.fake_docker_client.image_registry)

    def test_update_unmanaged_registry(self):
        self.loginUser()

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
            "registry_username": "user",
            "registry_password": "password",
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_registry = cast(BuildRegistry, BuildRegistry.objects.first())
        version_1 = new_registry.version
        initial_domain = new_registry.registry_domain
        self.assertIsNotNone(new_registry)

        # Update registry
        body = {
            "name": "My registry 2",
            "registry_username": "user2",
            "registry_password": "passworddd",
        }
        response = self.client.patch(
            reverse(
                "container_registry:build_registries.details",
                kwargs=dict(id=new_registry.id),
            ),
            data=body,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_registry.refresh_from_db()

        # version should be incremented on each update
        self.assertGreater(new_registry.version, version_1)
        self.assertEqual(new_registry.name, "My registry 2")
        self.assertEqual(new_registry.registry_username, "user2")
        self.assertEqual(new_registry.registry_password, "passworddd")
        self.assertEqual(new_registry.registry_domain, initial_domain)

    def test_update_registry_set_global_override_all_global(self):
        self.loginUser()

        body = {
            "name": "My registry",
            "is_managed": False,
            "is_global": True,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
            "registry_username": "user",
            "registry_password": "password",
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        body = {
            "name": "My registry 2",
            "is_managed": False,
            "is_global": False,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
            "registry_username": "user",
            "registry_password": "password",
        }
        response = self.client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        first_registry = cast(
            BuildRegistry, BuildRegistry.objects.filter(name="My registry").first()
        )
        self.assertIsNotNone(first_registry)
        second_registry = cast(
            BuildRegistry, BuildRegistry.objects.filter(name="My registry 2").first()
        )
        self.assertIsNotNone(second_registry)

        # Update registry
        body = {"is_global": True}
        response = self.client.patch(
            reverse(
                "container_registry:build_registries.details",
                kwargs=dict(id=second_registry.id),
            ),
            data=body,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        second_registry.refresh_from_db()
        first_registry.refresh_from_db()

        # version should be incremented on each update
        self.assertTrue(second_registry.is_global)
        self.assertFalse(first_registry.is_global)

    @responses.activate()
    async def test_update_managed_registry(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        body = {
            "name": "My registry",
            "is_managed": True,
            "is_global": True,
            "registry_domain": "registry.127.0.0.0.1.sslip.io",
            "registry_username": "hello",
            "registry_password": "hello",
        }
        response = await self.async_client.post(
            reverse("container_registry:build_registries.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        old_registry = cast(
            BuildRegistry,
            await BuildRegistry.objects.afirst(),
        )
        self.assertIsNotNone(old_registry)

        # Update registry
        body = {
            "name": "My registry 2",
            "registry_username": "zane",
            "registry_password": "supers3cr4tpassw4rd",
            "registry_domain": "registry.example.com",
        }
        response = await self.async_client.patch(
            reverse(
                "container_registry:build_registries.details",
                kwargs=dict(id=old_registry.id),
            ),
            data=body,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_registry = await BuildRegistry.objects.aget(pk=old_registry.id)

        # version should be incremented on each update
        self.assertGreater(new_registry.version, old_registry.version)
        self.assertEqual(new_registry.name, "My registry 2")
        self.assertEqual(new_registry.registry_username, "zane")
        self.assertEqual(new_registry.registry_password, "supers3cr4tpassw4rd")
        self.assertEqual(new_registry.registry_domain, "registry.example.com")

        # old configs should be deleted while new ones are created
        new_credentials_config = cast(
            FakeDockerClient.FakeConfig,
            self.fake_docker_client.config_map.get(
                get_config_name_for_registry(new_registry, "credentials")  # type: ignore
            ),
        )
        new_config_file = cast(
            FakeDockerClient.FakeConfig,
            self.fake_docker_client.config_map.get(
                get_config_name_for_registry(new_registry, "config")  # type: ignore
            ),
        )
        self.assertIsNotNone(new_credentials_config)
        self.assertIsNotNone(new_config_file)

        old_credentials_config = self.fake_docker_client.config_map.get(
            get_config_name_for_registry(old_registry, "credentials")  # type: ignore
        )
        old_config_file = self.fake_docker_client.config_map.get(
            get_config_name_for_registry(old_registry, "config")  # type: ignore
        )
        self.assertIsNone(old_credentials_config)
        self.assertIsNone(old_config_file)

        # check that the service config data has updated
        swarm_service = cast(
            FakeDockerClient.FakeService,
            self.fake_docker_client.service_map.get(
                cast(str, old_registry.swarm_service_name)
            ),
        )
        self.assertIsNotNone(swarm_service)
        self.assertIsNotNone(
            find_item_in_sequence(
                lambda c: c["ConfigID"] == new_config_file.id, swarm_service.configs
            )
        )
        self.assertIsNotNone(
            find_item_in_sequence(
                lambda c: c["ConfigID"] == new_credentials_config.id,
                swarm_service.configs,
            )
        )

        # the domain should also be udpated in caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_build_registry(
                cast(str, new_registry.service_alias), new_registry.registry_domain
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.get(
            ZaneProxyClient.get_uri_for_build_registry(
                cast(str, old_registry.service_alias), old_registry.registry_domain
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
