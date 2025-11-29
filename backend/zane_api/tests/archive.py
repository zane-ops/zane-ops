# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import (
    Project,
    Service,
    Deployment,
    PortConfiguration,
    URL,
    ArchivedDockerService,
    ArchivedGitService,
    EnvVariable,
    Volume,
    DeploymentChange,
    ArchivedURL,
    Config,
    DeploymentURL,
)
from temporal.activities import (
    ZaneProxyClient,
)
import requests


class DockerServiceArchiveViewTest(AuthAPITestCase):
    async def test_archive_simple_service(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        first_deployment = await service.deployments.select_related("service").afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = await Service.objects.filter(slug=service.slug).afirst()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(slug=service.slug).afirst()
        )
        self.assertIsNotNone(archived_service)

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            first_deployment
        )
        self.assertIsNone(deleted_docker_service)

        deployments = [
            deployment
            async for deployment in Deployment.objects.filter(
                service__slug=service.slug
            ).all()
        ]
        self.assertEqual(0, len(deployments))

    async def test_archive_non_deployed_service_deletes_the_service(self):
        p, service = await self.acreate_redis_docker_service()
        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = await Service.objects.filter(slug=service.slug).afirst()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(slug=service.slug).afirst()
        )
        self.assertIsNone(archived_service)

    async def test_archive_service_with_volume(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "name": "redis-data",
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                )
            ]
        )
        self.assertEqual(1, len(self.fake_docker_client.volume_map))
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_volume = await Volume.objects.filter(name="redis-data").afirst()
        self.assertIsNone(deleted_volume)

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("volumes")
            .afirst()
        )
        self.assertEqual(1, len(archived_service.volumes.all()))

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            deployment
        )
        self.assertIsNone(deleted_docker_service)
        self.assertEqual(0, len(self.fake_docker_client.volume_map))

    async def test_archive_service_with_config(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
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

        self.assertEqual(1, len(self.fake_docker_client.config_map))
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_config = await Config.objects.filter(name="caddyfile").afirst()
        self.assertIsNone(deleted_config)

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("configs")
            .afirst()
        )
        self.assertEqual(1, len(archived_service.configs.all()))

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            deployment
        )
        self.assertIsNone(deleted_docker_service)
        self.assertEqual(0, len(self.fake_docker_client.config_map))

    async def test_archive_service_with_env_and_command(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "REDIS_PASSWORD",
                        "value": "strongPassword123",
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.COMMAND,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value="redis-server --requirepass ${REDIS_PASSWORD}",
                ),
            ]
        )
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await EnvVariable.objects.filter(service__slug=service.slug).acount(),
        )

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("env_variables")
            .afirst()
        )
        self.assertEqual(1, await archived_service.env_variables.acount())

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            deployment
        )
        self.assertIsNone(deleted_docker_service)

    async def test_archive_service_with_resource_limits(self):
        resource_limits = {
            "cpus": 1.5,
            "memory": {"value": 500, "unit": "MEGABYTES"},
        }
        project, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value=resource_limits,
                ),
            ]
        )
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await EnvVariable.objects.filter(service__slug=service.slug).acount(),
        )

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id).afirst()
        )
        self.assertEqual(resource_limits, archived_service.resource_limits)

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            deployment
        )
        self.assertIsNone(deleted_docker_service)

    async def test_archive_service_with_port(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "host": 6379,
                        "forwarded": 6379,
                    },
                )
            ]
        )
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await PortConfiguration.objects.filter(service__slug=service.slug).acount(),
        )

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("ports")
            .afirst()
        )
        self.assertEqual(1, await archived_service.ports.acount())

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            deployment
        )
        self.assertIsNone(deleted_docker_service)

    async def test_archive_service_with_urls(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "thullo.fredkiss.dev",
                        "base_path": "/api",
                        "strip_prefix": True,
                        "associated_port": 80,
                    },
                )
            ]
        )
        deployment: Deployment = await service.deployments.afirst()
        first_deployment_url: DeploymentURL = await deployment.urls.afirst()
        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(
                service.id, await service.urls.afirst()
            ),
            timeout=5,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await URL.objects.filter(
                domain="thullo.fredkiss.dev", base_path="/api"
            ).acount(),
        )

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("urls")
            .afirst()
        )
        self.assertEqual(2, len(archived_service.urls.all()))
        url: ArchivedURL = await archived_service.urls.afirst()
        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(archived_service.original_id, url),
            timeout=5,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        response = requests.get(
            ZaneProxyClient.get_uri_for_deployment(
                deployment.hash, first_deployment_url.domain
            ),
            timeout=5,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            deployment
        )
        self.assertIsNone(deleted_docker_service)

    async def test_archive_service_non_existing(self):
        owner = await self.aLoginUser()
        p = await Project.objects.acreate(slug="kiss-cam", owner=owner)

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "env_slug": "production",
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_archive_should_delete_monitoring_tasks_for_the_deployment(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
            with_healthcheck=True
        )
        initial_deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await Deployment.objects.filter(service__slug=service.slug).acount(),
        )

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id).afirst()
        )
        self.assertIsNotNone(archived_service.healthcheck)
        self.assertIsNone(
            self.get_workflow_schedule_by_id(initial_deployment.monitor_schedule_id)
        )
        self.assertEqual(0, len(self.workflow_schedules))

    async def test_archive_should_delete_metrics_tasks_for_the_deployment(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await Deployment.objects.filter(service__slug=service.slug).acount(),
        )

        self.assertIsNone(
            self.get_workflow_schedule_by_id(initial_deployment.metrics_schedule_id)
        )
        self.assertEqual(0, len(self.workflow_schedules))


class GitServiceArchiveViewTest(AuthAPITestCase):
    async def test_archive_simple_git_service(self):
        project, service = await self.acreate_and_deploy_git_service()
        first_deployment = await service.deployments.select_related("service").afirst()
        response = await self.async_client.delete(
            reverse(
                "zane_api:services.git.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = await Service.objects.filter(slug=service.slug).afirst()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedGitService = await ArchivedGitService.objects.filter(
            slug=service.slug
        ).afirst()
        self.assertIsNotNone(archived_service)

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            first_deployment
        )
        self.assertIsNone(deleted_docker_service)

        deployments = [
            deployment
            async for deployment in Deployment.objects.filter(
                service__slug=service.slug
            ).all()
        ]
        self.assertEqual(0, len(deployments))
        deleted_docker_image = None
        for image in self.fake_docker_client.image_map.values():
            if await first_deployment.aimage_tag in image.tags:
                deleted_docker_image = image
                break
        self.assertIsNone(deleted_docker_image)
