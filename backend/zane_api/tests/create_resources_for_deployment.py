# type: ignore
from unittest.mock import patch, Mock
import requests
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import (
    Project,
    Deployment,
    Service,
    DeploymentChange,
    Volume,
    URL,
    SharedEnvVariable,
)

from temporal.activities import ZaneProxyClient

from ..utils import convert_value_to_bytes, jprint
from asgiref.sync import sync_to_async


class DockerServiceDeploymentCreateResourceTests(AuthAPITestCase):
    async def test_deploy_service_with_configs(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "contents": ':80 respond "hello from caddy"',
                        "mount_path": "/etc/caddy/Caddyfile",
                        "name": "caddyfile",
                        "language": "caddyfile",
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)  # type: ignore

        self.assertIsNotNone(docker_service)
        self.assertEqual(1, len(self.fake_docker_client.config_map))
        self.assertEqual(1, len(docker_service.configs))  # type: ignore

        new_config = await service.configs.afirst()
        self.assertIsNotNone(docker_service.get_attached_config(new_config))

    async def test_deploy_service_with_urls(
        self,
    ):
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 80,
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server2.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "redirect_to": {
                            "url": "https://web-server.fred.kiss",
                            "permanent": True,
                        },
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server3.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "redirect_to": {
                            "url": "https://web-server.fred.kiss",
                            "permanent": False,
                        },
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        service_url: URL = await service.urls.filter(
            domain="web-server.fred.kiss"
        ).afirst()
        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(service.id, service_url)
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.get(
            ZaneProxyClient.get_uri_for_deployment(
                new_deployment.hash, (await new_deployment.urls.afirst()).domain
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    async def test_deploy_simple_service(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)

    async def test_deploy_service_with_env(self):
        await self.aLoginUser()
        p, service = await self.acreate_redis_docker_service()
        service: Service = await (
            Service.objects.filter(id=service.id)
            .select_related("environment")
            .prefetch_related("env_variables")
            .afirst()
        )

        # add env in service with the same name
        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "REDIS_USERNAME",
                        "value": "super-secret",
                    },
                ),
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "REDIS_PASSWORD",
                        "value": "super-secret-key-value-random123",
                    },
                ),
            ]
        )

        await SharedEnvVariable.objects.abulk_create(
            [
                SharedEnvVariable(
                    key="GITHUB_CLIENT_ID",
                    value="superSecret",
                    environment=service.environment,
                ),
                SharedEnvVariable(
                    key="GITHUB_TOKEN",
                    value="superSecret",
                    environment=service.environment,
                ),
            ]
        )
        # deploy service
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        jprint(docker_service.env)

        # Include all service env variables
        self.assertTrue(
            all(
                [
                    env.key in docker_service.env
                    async for env in service.env_variables.all()
                ]
            )
        )
        envv = [
            (env.key, env.value) async for env in service.environment.variables.all()
        ]
        print(f"{docker_service.env=}")
        print(f"{envv=}")
        # Include all environment variables
        self.assertTrue(
            all(
                [
                    env.key in docker_service.env
                    async for env in service.environment.variables.all()
                ]
            )
        )
        # Include all system variables
        self.assertTrue(
            all(
                [
                    env["key"] in docker_service.env
                    for env in await sync_to_async(
                        lambda: service.system_env_variables
                    )()
                ]
            )
        )

    async def test_deploy_service_with_volumes(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)

        self.assertIsNotNone(docker_service)
        self.assertEqual(1, len(self.fake_docker_client.volume_map))
        self.assertEqual(1, len(docker_service.attached_volumes))

        new_volume = await service.volumes.afirst()
        self.assertIsNotNone(docker_service.get_attached_volume(new_volume))

    async def test_deploy_service_with_resource_limits(self):
        await self.aLoginUser()
        resource_limits = {
            "cpus": 1.5,
            "memory": {"value": 500, "unit": "MEGABYTES"},
        }
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value=resource_limits,
                ),
            ]
        )
        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        self.assertIsNotNone(docker_service.resources)

        nano_cpus = resource_limits.get("cpus") * 1e9
        memory_bytes = convert_value_to_bytes(
            value=resource_limits.get("memory")["value"],
            unit=resource_limits.get("memory")["unit"],
        )
        self.assertEqual(
            nano_cpus, docker_service.resources.get("Limits").get("NanoCPUs")
        )
        self.assertEqual(
            memory_bytes, docker_service.resources.get("Limits").get("MemoryBytes")
        )

    async def test_deploy_service_with_volumes_do_not_create_resources_for_volumes_with_host_path(
        self,
    ):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "host_path": "/var/www/caddy/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

        self.assertEqual(0, len(self.fake_docker_client.volume_map))
        self.assertEqual(1, len(docker_service.attached_volumes))

    async def test_deploy_service_with_volumes_do_not_include_deleted_volumes(
        self,
    ):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/delete",
                        "host_path": "/delete",
                        "mode": Volume.VolumeMode.READ_ONLY,
                    },
                ),
            ]
        )
        volume_to_delete = await service.volumes.filter(host_path="/delete").afirst()
        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=volume_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)

        self.assertIsNotNone(docker_service)
        self.assertEqual(1, len(docker_service.attached_volumes))
        self.assertIsNone(docker_service.get_attached_volume(volume_to_delete))

    async def test_deploy_service_with_port(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"host": 6383, "forwarded": 6379},
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)

        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        self.assertIsNotNone(docker_service.endpoint)

        port_in_docker = docker_service.endpoint.get("Ports")[0]
        self.assertEqual(6383, port_in_docker["PublishedPort"])
        self.assertEqual(6379, port_in_docker["TargetPort"])

    async def test_deploy_service_set_started_at(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service()
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.started_at)

    async def test_deploy_service_set_finished_at_on_success(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service()
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.finished_at)

    @patch("temporal.activities.main_activities.monotonic")
    async def test_deploy_service_set_finished_at_on_fail(
        self,
        mock_monotonic: Mock,
    ):
        mock_monotonic.side_effect = [0, 31]
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        new_deployment: Deployment = await service.deployments.afirst()
        self.assertIsNotNone(new_deployment.finished_at)

    @patch("temporal.activities.main_activities.monotonic")
    async def test_deploy_service_set_deployment_failed_when_healthcheck_fails(
        self,
        mock_monotonic: Mock,
    ):
        mock_monotonic.side_effect = [0, 31]
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        new_deployment: Deployment = await service.deployments.afirst()
        self.assertEqual(Deployment.DeploymentStatus.FAILED, new_deployment.status)

    @patch("temporal.activities.main_activities.monotonic")
    async def test_deploy_service_set_deployment_to_production_when_healthcheck_fails_if_unique(
        self,
        mock_monotonic: Mock,
    ):
        mock_monotonic.side_effect = [0, 31]
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        new_deployment: Deployment = await service.deployments.afirst()
        self.assertEqual(Deployment.DeploymentStatus.FAILED, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)

    async def test_deploy_service_do_not_set_deployment_to_production_when_healthcheck_fails(
        self,
    ):
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 30]
            response = await self.async_client.put(
                reverse(
                    "zane_api:services.docker.deploy_service",
                    kwargs={
                        "project_slug": p.slug,
                        "env_slug": "production",
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment: Deployment = await service.deployments.afirst()
        self.assertEqual(Deployment.DeploymentStatus.FAILED, new_deployment.status)
        self.assertFalse(new_deployment.is_current_production)

    async def test_set_deployment_as_failed_when_image_fails_to_pull(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = await Project.objects.aget(slug="zane-ops")

        create_service_payload = {
            "slug": "app",
            "image": "redis:alpine",
        }
        response = await self.async_client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = await Service.objects.aget(slug="app")

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "image": self.fake_docker_client.NONEXISTANT_IMAGE,
                    },
                    service=service,
                ),
            ]
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        first_deployment: Deployment = await service.deployments.afirst()

        self.assertEqual(Deployment.DeploymentStatus.FAILED, first_deployment.status)
        self.assertIsNotNone(first_deployment.status_reason)
        self.assertIsNotNone(first_deployment.finished_at)

    async def test_clean_non_cleaned_up_previous_deployments_if_weird_error(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        first_deployment = await service.deployments.aearliest("queued_at")
        first_deployment.status = Deployment.DeploymentStatus.HEALTHY
        await first_deployment.asave()

        second_deployment = await service.deployments.filter(
            queued_at__gt=first_deployment.queued_at
        ).aearliest("queued_at")
        second_deployment.status = Deployment.DeploymentStatus.UNHEALTHY
        await second_deployment.asave()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        first_deployment = await service.deployments.aearliest("queued_at")
        self.assertEqual(Deployment.DeploymentStatus.REMOVED, first_deployment.status)
        second_deployment = await service.deployments.filter(
            queued_at__gt=first_deployment.queued_at
        ).aearliest("queued_at")
        self.assertEqual(Deployment.DeploymentStatus.REMOVED, second_deployment.status)
