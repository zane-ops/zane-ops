import json
import re
from unittest.mock import patch, MagicMock

import requests
import responses
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from temporalio.testing import WorkflowEnvironment

from .base import AuthAPITestCase
from ..dtos import HealthCheckDto
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    PortConfiguration,
    URL,
    ArchivedDockerService,
    DockerEnvVariable,
    Volume,
    DockerDeploymentChange,
    HealthCheck,
    ArchivedURL,
)
from ..temporal import (
    MonitorDockerDeploymentWorkflow,
    HealthcheckDeploymentDetails,
    SimpleDeploymentDetails,
    ZaneProxyClient,
)


class DockerServiceCreateViewTest(AuthAPITestCase):

    def test_create_simple_service(self):
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
        data = response.json()
        self.assertIsNotNone(data)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(created_service)

    def test_create_service_with_custom_registry(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertTrue(self.fake_docker_client.is_logged_in)

    def test_create_service_with_empty_credentials_do_not_save_the_credentials(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "",
                "password": "",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNotNone(created_service)
        credentials_changes = created_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.CREDENTIALS
        ).first()
        self.assertIsNone(credentials_changes)

    def test_create_service_slug_is_created_if_not_specified(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = DockerRegistryService.objects.filter().first()
        self.assertIsNotNone(created_service)
        self.assertIsNotNone(created_service.slug)

    def test_create_service_slug_is_lowercased(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zane-ops", owner=owner)

        create_service_payload = {
            "slug": "Zane-Ops-fronT",
            "image": "ghcr.io/zane-ops-front:latest",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = DockerRegistryService.objects.filter(
            slug="zane-ops-front"
        ).first()
        self.assertIsNotNone(created_service)

    def test_create_service_slug_accept_underscores(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zane-ops", owner=owner)

        create_service_payload = {
            "slug": "hello_nginx",
            "image": "nginxdemos/hello:latest",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "hello_nginx"},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_create_service_set_network_alias(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "valkey",
            "image": "valkey:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="valkey"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertIsNotNone(created_service.network_alias)

    def test_create_service_bad_request(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    def test_create_service_for_nonexistent_project(self):
        self.loginUser()
        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "gh-clone"}
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    def test_create_service_conflict_with_slug(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        DockerRegistryService.objects.create(slug="cache-db", image="redis", project=p)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_create_service_with_custom_registry_does_not_create_service_if_bad_image_credentials(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "bad",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    def test_create_service_with_custom_registry_does_not_create_service_if_nonexistent_image(
        self,
    ):
        owner = self.loginUser()

        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": self.fake_docker_client.NONEXISTANT_PRIVATE_IMAGE,
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    def test_create_service_credentials_do_not_correspond_to_image(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "gcr.io/redis:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "bad",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    def test_create_service_with_service_if_nonexistent_dockerhub_image(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": self.fake_docker_client.NONEXISTANT_IMAGE,
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)


class DockerServiceHealthCheckViewTests(AuthAPITestCase):
    async def test_create_scheduled_task_when_deploying_a_service(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        initial_deployment: DockerDeployment = (
            await service.alatest_production_deployment
        )
        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(
            self.get_workflow_schedule_by_id(initial_deployment.monitor_schedule_id)
        )

    async def test_create_service_do_not_create_monitor_task_when_deployment_fails(
        self,
    ):
        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            p, service = await self.acreate_and_deploy_redis_docker_service()

        latest_deployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )
        self.assertIsNone(
            self.get_workflow_schedule_by_id(latest_deployment.monitor_schedule_id)
        )

    async def test_create_scheduled_task_with_healthcheck_same_interval(self):
        p, service = await self.acreate_and_deploy_redis_docker_service(
            with_healthcheck=True
        )

        initial_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(
            DockerDeployment.DeploymentStatus.HEALTHY,
            initial_deployment.status,
        )
        schedule_handle = self.get_workflow_schedule_by_id(
            initial_deployment.monitor_schedule_id
        )
        self.assertIsNotNone(schedule_handle)
        self.assertEqual(
            initial_deployment.service.healthcheck.interval_seconds,
            schedule_handle.interval.seconds,
        )

    @responses.activate
    async def test_create_service_with_healtheck_path_success(self):
        deployment_url_pattern = re.compile(
            rf"^(?!{re.escape(settings.CADDY_PROXY_ADMIN_HOST)}).*{re.escape(settings.ROOT_DOMAIN)}"
        )
        responses.add(
            responses.GET,
            url=re.compile(deployment_url_pattern),
            status=status.HTTP_200_OK,
        )
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)

        p, service = await self.acreate_and_deploy_caddy_docker_service(
            with_healthcheck=True
        )
        latest_deployment = await service.alatest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    @responses.activate
    async def test_create_service_with_healtheck_path_error(self):
        deployment_url_pattern = re.compile(
            rf"^(?!{re.escape(settings.CADDY_PROXY_ADMIN_HOST)}).*{re.escape(settings.ROOT_DOMAIN)}"
        )
        responses.add(
            responses.GET,
            url=re.compile(deployment_url_pattern),
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)

        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 0, 0, 31]
            p, service = await self.acreate_and_deploy_caddy_docker_service(
                with_healthcheck=True
            )

        latest_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    async def test_create_service_with_healtheck_cmd_success(self):
        _, service = await self.acreate_and_deploy_redis_docker_service(
            with_healthcheck=True
        )
        latest_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    async def test_create_service_with_healtheck_cmd_error(self):
        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 0, 0, 31]
            _, service = await self.acreate_and_deploy_redis_docker_service(
                other_changes=[
                    DockerDeploymentChange(
                        field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                        type=DockerDeploymentChange.ChangeType.UPDATE,
                        new_value={
                            "type": "COMMAND",
                            "value": self.fake_docker_client.FAILING_CMD,
                            "timeout_seconds": 30,
                            "interval_seconds": 15,
                        },
                    ),
                ]
            )

        latest_deployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    async def test_create_service_without_healthcheck_succeed_when_service_is_working_correctly_by_default(
        self,
    ):
        _, service = await self.acreate_and_deploy_redis_docker_service()
        latest_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(latest_deployment)
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    async def test_create_service_without_healthcheck_deployment_is_set_to_failed_when_docker_fails_to_start(
        self,
    ):
        class MockService:
            def __init__(self, name: str):
                self.name = name

            @staticmethod
            def tasks(*args, **kwargs):
                return []

            def scale(self, *args):
                pass

            def remove(self):
                pass

        self.fake_docker_client.services.get = lambda _id: MockService(_id)

        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 0, 0, 31]
            p, service = await self.acreate_and_deploy_redis_docker_service()

        latest_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    async def test_create_service_scale_down_service_to_zero_when_deployment_fails(
        self,
    ):
        fake_service = MagicMock()
        fake_service.tasks.return_value = []
        self.fake_docker_client.services.get = lambda _id: fake_service

        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            p, service = await self.acreate_and_deploy_redis_docker_service()

        latest_deployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )
        fake_service.scale.assert_called_with(0)


class DockerGetServiceViewTest(AuthAPITestCase):
    def test_get_service_succesful(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(slug="cache-db", project=p)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_get_service_non_existing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_get_service_not_in_the_correct_project(self):
        owner = self.loginUser()
        p1 = Project.objects.create(slug="kiss-cam", owner=owner)
        p2 = Project.objects.create(slug="camly", owner=owner)

        service = DockerRegistryService.objects.create(slug="cache-db", project=p1)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p2.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DockerServiceUpdateViewTest(AuthAPITestCase):
    def test_sucessfully_update_service_slug(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        previous_service = DockerRegistryService.objects.create(
            slug="cache-db", project=p
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": previous_service.slug},
            ),
            data={
                "slug": "cache",
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache"
        ).first()
        self.assertIsNotNone(updated_service)
        self.assertEqual("cache", updated_service.slug)
        self.assertNotEquals(previous_service.updated_at, updated_service.updated_at)

    def test_update_service_bad_request(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)
        service = DockerRegistryService.objects.create(slug="cache-db", project=p)

        response = self.client.patch(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data={
                "slug": "cache db",
            },
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_service_non_existent(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)
        response = self.client.patch(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "zane-ops"},
            ),
            data={"slug": "zenops"},
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_already_existing_slug(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)
        DockerRegistryService.objects.bulk_create(
            [
                DockerRegistryService(slug="gh-clone", project=p),
                DockerRegistryService(slug="zane-ops", project=p),
            ]
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "zane-ops"},
            ),
            data={"slug": "gh-clone"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_can_rename_to_self(self):
        owner = self.loginUser()
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)
        DockerRegistryService.objects.bulk_create(
            [
                DockerRegistryService(slug="gh-clone", project=p),
                DockerRegistryService(slug="zane-ops", project=p),
            ]
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "zane-ops"},
            ),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class DockerServiceArchiveViewTest(AuthAPITestCase):
    async def test_archive_simple_service(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        first_deployment = await service.deployments.select_related("service").afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = await DockerRegistryService.objects.filter(
            slug=service.slug
        ).afirst()
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
            async for deployment in DockerDeployment.objects.filter(
                service__slug=service.slug
            ).all()
        ]
        self.assertEqual(0, len(deployments))

    async def test_archive_non_deployed_service_deletes_the_service(self):
        owner = await self.aLoginUser()
        project = await Project.objects.acreate(slug="zaneops", owner=owner)
        service = await DockerRegistryService.objects.acreate(
            slug="app", project=project
        )

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = await DockerRegistryService.objects.filter(
            slug=service.slug
        ).afirst()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(slug=service.slug).afirst()
        )
        self.assertIsNone(archived_service)

    async def test_archive_service_with_volume(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
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

    async def test_archive_service_with_env_and_command(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "REDIS_PASSWORD",
                        "value": "strongPassword123",
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.COMMAND,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="redis-server --requirepass ${REDIS_PASSWORD}",
                ),
            ]
        )
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await DockerEnvVariable.objects.filter(service__slug=service.slug).acount(),
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
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value=resource_limits,
                ),
            ]
        )
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await DockerEnvVariable.objects.filter(service__slug=service.slug).acount(),
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
        project, service = await self.acreate_and_deploy_caddy_docker_service()
        deployment = await service.deployments.afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await PortConfiguration.objects.filter(
                dockerregistryservice__slug=service.slug
            ).acount(),
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
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "thullo.fredkiss.dev",
                        "base_path": "/api",
                        "strip_prefix": True,
                    },
                )
            ]
        )
        deployment: DockerDeployment = await service.deployments.afirst()
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
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
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
        self.assertEqual(1, len(archived_service.urls.all()))
        url: ArchivedURL = await archived_service.urls.afirst()
        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(archived_service.original_id, url),
            timeout=5,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        response = requests.get(
            ZaneProxyClient.get_uri_for_deployment(deployment.hash),
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
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
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
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await DockerDeployment.objects.filter(service__slug=service.slug).acount(),
        )

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(original_id=service.id).afirst()
        )
        self.assertIsNotNone(archived_service.healthcheck)
        self.assertIsNone(
            self.get_workflow_schedule_by_id(initial_deployment.monitor_schedule_id)
        )
        self.assertEqual(0, len(self.workflow_schedules))


class DockerServiceMonitorTests(AuthAPITestCase):
    async def test_normal_deployment_flow(self):
        async with self.workflowEnvironment() as env:  # type: WorkflowEnvironment
            owner = await self.aLoginUser()
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            token = await Token.objects.aget(user=owner)
            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                auth_token=token.key,
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

    async def test_restart_is_set_after_multiple_tasks_deployments(self):
        async with self.workflowEnvironment() as env:  # type: WorkflowEnvironment
            owner = await self.aLoginUser()
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return [
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdkg",
                            "Version": {"Index": 15078},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "shutdown",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 127,
                                },
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                            "Version": {"Index": 15079},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "starting",
                                "Message": "started",
                                # "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 0,
                                },
                            },
                            "DesiredState": "starting",
                        },
                    ]

            self.fake_docker_client.services.get = lambda _id: FakeService()

            token = await Token.objects.aget(user=owner)
            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                auth_token=token.key,
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.RESTARTING,
                latest_deployment.status,
            )

    async def test_succesful_restart_deployment_flow(self):
        async with self.workflowEnvironment() as env:  # type: WorkflowEnvironment
            owner = await self.aLoginUser()
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return [
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdkg",
                            "Version": {"Index": 15078},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "shutdown",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 127,
                                },
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                            "Version": {"Index": 15079},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "running",
                                "Message": "started",
                                # "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 0,
                                },
                            },
                            "DesiredState": "running",
                        },
                    ]

            self.fake_docker_client.services.get = lambda _id: FakeService()

            token = await Token.objects.aget(user=owner)
            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                auth_token=token.key,
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

    async def test_unsuccesful_restart_deployment_flow(self):
        async with self.workflowEnvironment() as env:  # type: WorkflowEnvironment
            owner = await self.aLoginUser()
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return [
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                            "Version": {"Index": 15078},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "a6e983977676b708ed0201c91c4fa3c6fbc4c1d43f7520327db8efc5ba8b76f0",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "jumpidf77nnc9u24dn2t0t8gk",
                            "Version": {"Index": 15070},
                            "CreatedAt": "2024-04-25T20:11:21.303508844Z",
                            "UpdatedAt": "2024-04-25T20:11:32.93669947Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:32.642315167Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "407c4b40d621b127a1cac498d066587522f4ddcca1ec01992dbf94f49c6092fc",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "wqnwod7cacovpscsp3n6vsgmc",
                            "Version": {"Index": 15091},
                            "CreatedAt": "2024-04-25T20:11:52.686304192Z",
                            "UpdatedAt": "2024-04-25T20:12:02.693438335Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:12:02.415795453Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "edd2aa5d80747f860b1cee700a1028e7000970f05a8fe9784fa0f81c460459ac",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "wwkdns3g7fsyq37hwe5cj7spl",
                            "Version": {"Index": 15086},
                            "CreatedAt": "2024-04-25T20:11:42.863807131Z",
                            "UpdatedAt": "2024-04-25T20:11:52.887691861Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:52.620438735Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "f45b1785bca08314c9b6af63bdf8080aa79d60a427315d9fe96ba8928d1d1d54",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                    ]

            self.fake_docker_client.services.get = lambda _id: FakeService()

            token = await Token.objects.aget(user=owner)
            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                auth_token=token.key,
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.UNHEALTHY,
                latest_deployment.status,
            )

    async def test_service_fail_outside_of_zane_control(self):
        async with self.workflowEnvironment() as env:  # type: WorkflowEnvironment
            owner = await self.aLoginUser()
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return []

            self.fake_docker_client.services.get = lambda _id: FakeService()

            token = await Token.objects.aget(user=owner)
            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                auth_token=token.key,
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment
            self.assertEqual(
                DockerDeployment.DeploymentStatus.UNHEALTHY,
                latest_deployment.status,
            )
