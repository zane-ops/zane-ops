# type: ignore
import json
import re
from unittest.mock import patch, MagicMock

import responses
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import (
    Project,
    Service,
    Deployment,
    DeploymentChange,
)


class DockerServiceCreateViewTest(AuthAPITestCase):
    def test_create_simple_service(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertIsNotNone(data)

        created_service: Service = Service.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)

    def test_create_service_with_custom_registry(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
            },
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNotNone(created_service)
        self.assertTrue(self.fake_docker_client.is_logged_in)

    def test_create_service_with_empty_credentials_do_not_save_the_credentials(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "",
                "password": "",
            },
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNotNone(created_service)
        change = created_service.unapplied_changes.filter(
            field=DeploymentChange.ChangeField.SOURCE
        ).first()
        self.assertIsNone(change.new_value.get("credentials"))

    def test_create_service_slug_is_created_if_not_specified(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = Service.objects.filter().first()
        self.assertIsNotNone(created_service)
        self.assertIsNotNone(created_service.slug)

    def test_create_service_slug_is_lowercased(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "Zane-Ops-fronT",
            "image": "ghcr.io/zane-ops-front:latest",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = Service.objects.filter(slug="zane-ops-front").first()
        self.assertIsNotNone(created_service)

    def test_create_service_slug_accept_underscores(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "hello_nginx",
            "image": "nginxdemos/hello:latest",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": "hello_nginx",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_create_service_set_network_alias(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "valkey",
            "image": "valkey:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: Service = Service.objects.filter(slug="valkey").first()
        self.assertIsNotNone(created_service)
        self.assertIsNotNone(created_service.network_alias)

    def test_create_service_bad_request(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNone(created_service)

    def test_create_service_for_nonexistent_project(self):
        self.loginUser()
        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": "gh-clone", "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNone(created_service)

    def test_create_service_conflict_with_slug(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        Service.objects.create(
            slug="cache-db", image="redis", project=p, environment=p.production_env
        )

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_create_service_with_custom_registry_does_not_create_service_if_nonexistent_image(
        self,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": self.fake_docker_client.NONEXISTANT_IMAGE,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNone(created_service)

    def test_create_service_credentials_do_not_correspond_to_image(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "gh-clone"},
        )
        p = Project.objects.get(slug="gh-clone")

        create_service_payload = {
            "slug": "main-app",
            "image": "gcr.io/redis:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "bad",
            },
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNone(created_service)

    def test_create_service_with_service_if_nonexistent_dockerhub_image(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": self.fake_docker_client.NONEXISTANT_IMAGE,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNone(created_service)


class DockerServiceHealthCheckViewTests(AuthAPITestCase):
    async def test_create_scheduled_task_when_deploying_a_service(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        initial_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(
            self.get_workflow_schedule_by_id(initial_deployment.monitor_schedule_id)
        )

    async def test_create_service_do_not_create_monitor_task_when_deployment_fails(
        self,
    ):
        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            p, service = await self.acreate_and_deploy_redis_docker_service()

        latest_deployment = await service.deployments.afirst()
        self.assertEqual(
            Deployment.DeploymentStatus.FAILED,
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
            Deployment.DeploymentStatus.HEALTHY,
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
            r"http:\/\/[a-z0-9]{12}:\d+/.*", re.IGNORECASE
        )
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        responses.add(
            responses.GET,
            url=re.compile(deployment_url_pattern),
            status=status.HTTP_200_OK,
        )

        p, service = await self.acreate_and_deploy_caddy_docker_service(
            with_healthcheck=True
        )
        latest_deployment = await service.alatest_production_deployment
        self.assertEqual(
            Deployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    @responses.activate
    async def test_create_service_with_healtheck_path_error(self):
        deployment_url_pattern = re.compile(
            r"http:\/\/[a-z0-9]{12}:\d+/.*", re.IGNORECASE
        )
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        responses.add(
            responses.GET,
            url=re.compile(deployment_url_pattern),
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 0, 0, 31]
            p, service = await self.acreate_and_deploy_caddy_docker_service(
                with_healthcheck=True
            )

        latest_deployment: Deployment = await service.deployments.afirst()
        self.assertEqual(
            Deployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    async def test_create_service_with_healtheck_cmd_success(self):
        _, service = await self.acreate_and_deploy_redis_docker_service(
            with_healthcheck=True
        )
        latest_deployment: Deployment = await service.deployments.afirst()
        self.assertEqual(
            Deployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    async def test_create_service_with_healtheck_cmd_error(self):
        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 0, 0, 31]
            _, service = await self.acreate_and_deploy_redis_docker_service(
                other_changes=[
                    DeploymentChange(
                        field=DeploymentChange.ChangeField.HEALTHCHECK,
                        type=DeploymentChange.ChangeType.UPDATE,
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
            Deployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    async def test_create_service_without_healthcheck_succeed_when_service_is_working_correctly_by_default(
        self,
    ):
        _, service = await self.acreate_and_deploy_redis_docker_service()
        latest_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(latest_deployment)
        self.assertEqual(
            Deployment.DeploymentStatus.HEALTHY,
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

        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 0, 0, 31]
            p, service = await self.acreate_and_deploy_redis_docker_service()

        latest_deployment: Deployment = await service.deployments.afirst()
        self.assertEqual(
            Deployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    async def test_create_service_scale_down_service_to_zero_when_deployment_fails(
        self,
    ):
        fake_service = MagicMock()
        fake_service.tasks.return_value = []
        self.fake_docker_client.services.get = lambda _id: fake_service

        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            p, service = await self.acreate_and_deploy_redis_docker_service()

        latest_deployment = await service.deployments.afirst()
        self.assertEqual(
            Deployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )
        fake_service.scale.assert_called_with(0)


class DockerGetServiceViewTest(AuthAPITestCase):
    def test_get_service_succesful(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        service = Service.objects.create(
            slug="cache-db", project=p, environment=p.production_env
        )

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_get_service_non_existing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": "cache-db",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_get_service_not_in_the_correct_project(self):
        owner = self.loginUser()
        p1 = Project.objects.create(slug="kiss-cam", owner=owner)
        p1.environments.create(name="production")
        p2 = Project.objects.create(slug="camly", owner=owner)
        p2.environments.create(name="production")

        service = Service.objects.create(
            slug="cache-db", project=p1, environment=p1.production_env
        )

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p2.slug,
                    "env_slug": "production",
                    "slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DockerServiceUpdateViewTest(AuthAPITestCase):
    def test_sucessfully_update_service_slug(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        previous_service = Service.objects.create(
            slug="cache-db", project=p, environment=p.production_env
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": previous_service.slug,
                },
            ),
            data={
                "slug": "cache",
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service: Service = Service.objects.filter(slug="cache").first()
        self.assertIsNotNone(updated_service)
        self.assertEqual("cache", updated_service.slug)
        self.assertNotEqual(previous_service.updated_at, updated_service.updated_at)

    def test_update_service_bad_request(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")
        service = Service.objects.create(
            slug="cache-db", project=p, environment=p.production_env
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": service.slug,
                },
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
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": "zane-ops",
                },
            ),
            data={"slug": "zenops"},
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_already_existing_slug(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")
        Service.objects.bulk_create(
            [
                Service(slug="gh-clone", project=p, environment=p.production_env),
                Service(slug="zane-ops", project=p, environment=p.production_env),
            ]
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": "zane-ops",
                },
            ),
            data={"slug": "gh-clone"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_can_rename_to_self(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")
        Service.objects.bulk_create(
            [
                Service(slug="gh-clone", project=p, environment=p.production_env),
                Service(slug="zane-ops", project=p, environment=p.production_env),
            ]
        )

        response = self.client.patch(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": "zane-ops",
                },
            ),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
