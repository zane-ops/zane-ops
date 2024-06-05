import json
import re
from unittest.mock import patch, Mock, MagicMock

import responses
from django.urls import reverse
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from rest_framework import status
from rest_framework.authtoken.models import Token

from .base import AuthAPITestCase, FakeDockerClient
from ..docker_operations import (
    get_swarm_service_name_for_deployment,
)
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
)
from ..tasks import monitor_docker_service_deployment


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
                "registry_url": "https://dcr.fredkiss.dev/",
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
    def test_create_scheduled_task_when_deploying_a_service(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        initial_deployment: DockerDeployment = service.latest_production_deployment
        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(initial_deployment.monitor_task)

    @patch("zane_api.docker_operations.sleep")
    @patch("zane_api.docker_operations.monotonic")
    def test_create_service_do_not_create_monitor_task_when_deployment_fails(
        self, mock_monotonic: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        mock_monotonic.side_effect = [0, 31]

        fake_service = MagicMock()
        fake_service.tasks.return_value = []
        self.fake_docker_client.services.get = lambda _id: fake_service

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        latest_deployment = service.deployments.first()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )
        self.assertIsNone(latest_deployment.monitor_task)

    def test_create_scheduled_task_with_healthcheck_same_interval(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "redis-cli PING",
                        "timeout_seconds": 30,
                        "interval_seconds": 15,
                    },
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        initial_deployment = service.latest_production_deployment
        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(
            DockerDeployment.DeploymentStatus.HEALTHY,
            initial_deployment.status,
        )
        self.assertIsNotNone(initial_deployment.monitor_task)
        self.assertEqual(15, initial_deployment.monitor_task.interval.every)

    @responses.activate
    def test_create_service_with_healtheck_path_success(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                    },
                    service=service,
                ),
            ]
        )

        responses.add(
            responses.GET,
            url=re.compile("^(https?)*"),
            status=status.HTTP_200_OK,
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    @responses.activate
    @patch("zane_api.docker_operations.sleep")
    @patch("zane_api.docker_operations.monotonic")
    def test_create_service_with_healtheck_path_error(
        self,
        mock_monotonic: Mock,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"type": "PATH", "value": "/", "timeout_seconds": 30},
                    service=service,
                ),
            ]
        )

        responses.add(
            responses.GET,
            url=re.compile("^(https?)*"),
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        mock_monotonic.side_effect = [0, 0, 0, 31]

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment: DockerDeployment = service.deployments.first()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    def test_create_service_with_healtheck_cmd_success(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="redis:alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "redis-cli PING",
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment: DockerDeployment = service.deployments.first()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    @patch("zane_api.docker_operations.sleep")
    @patch("zane_api.docker_operations.monotonic")
    def test_create_service_with_healtheck_cmd_error(
        self,
        mock_monotonic: Mock,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="redis:alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": FakeDockerClient.FAILING_CMD,
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
            ]
        )

        mock_monotonic.side_effect = [0, 0, 0, 31]

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        latest_deployment = service.deployments.first()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )

    def test_create_service_without_healthcheck_succeed_when_service_is_working_correctly_by_default(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.latest_production_deployment
        self.assertIsNotNone(latest_deployment)
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    @patch("zane_api.docker_operations.sleep")
    @patch("zane_api.docker_operations.monotonic")
    def test_create_service_without_healthcheck_deployment_is_set_to_failed_when_docker_fails_to_start(
        self,
        mock_monotonic: Mock,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        mock_monotonic.side_effect = [0, 0, 0, 31]

        class FakeService:
            @staticmethod
            def tasks(*args, **kwargs):
                return []

            def scale(self, *args):
                pass

        self.fake_docker_client.services.get = lambda _id: FakeService()

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        latest_deployment: DockerDeployment = service.deployments.first()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED,
            latest_deployment.status,
        )
        self.assertFalse(latest_deployment.is_current_production)

    @patch("zane_api.docker_operations.sleep")
    @patch("zane_api.docker_operations.monotonic")
    def test_create_service_scale_down_service_to_zero_when_deployment_fails(
        self,
        mock_monotonic: Mock,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        mock_monotonic.side_effect = [0, 31]

        fake_service = MagicMock()
        fake_service.tasks.return_value = []
        self.fake_docker_client.services.get = lambda _id: fake_service

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.deployments.first()
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


class DockerServiceArchiveViewTest(AuthAPITestCase):
    def test_archive_simple_service(self):
        project, service = self.create_and_deploy_REDIS_docker_service()
        first_deployment = service.deployments.first()

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = DockerRegistryService.objects.filter(
            slug=service.slug
        ).first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = ArchivedDockerService.objects.filter(
            slug=service.slug
        ).first()
        self.assertIsNotNone(archived_service)

        deleted_docker_service = self.fake_docker_client.service_map.get(
            get_swarm_service_name_for_deployment(first_deployment)
        )
        self.assertIsNone(deleted_docker_service)

        deployments = DockerDeployment.objects.filter(service__slug=service.slug)
        self.assertEqual(0, len(deployments))

    def test_archive_non_deployed_service_deletes_the_service(self):
        owner = self.loginUser()
        project = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=project)

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = DockerRegistryService.objects.filter(
            slug=service.slug
        ).first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = ArchivedDockerService.objects.filter(
            slug=service.slug
        ).first()
        self.assertIsNone(archived_service)

    def test_archive_service_with_volume(self):
        project, service = self.create_and_deploy_REDIS_docker_service(
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
        deployment = service.deployments.first()

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_volumes = Volume.objects.filter(name="redis-data")
        self.assertEqual(0, len(deleted_volumes))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(
                original_id=service.id
            ).prefetch_related("volumes")
        ).first()
        self.assertEqual(1, len(archived_service.volumes.all()))

        service_name = get_swarm_service_name_for_deployment(
            (
                archived_service.project.original_id,
                archived_service.original_id,
                archived_service.deployment_hashes[0],
            )
        )
        deleted_docker_service = self.fake_docker_client.service_map.get(service_name)
        self.assertIsNone(deleted_docker_service)
        self.assertEqual(0, len(self.fake_docker_client.volume_map))

    def test_archive_service_with_env_and_command(self):
        project, service = self.create_and_deploy_REDIS_docker_service(
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
        deployment = service.deployments.first()

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0, DockerEnvVariable.objects.filter(service__slug=service.slug).count()
        )

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(
                original_id=service.id
            ).prefetch_related("env_variables")
        ).first()
        self.assertEqual(1, archived_service.env_variables.count())

        service_name = get_swarm_service_name_for_deployment(
            (
                archived_service.project.original_id,
                archived_service.original_id,
                archived_service.deployment_hashes[0],
            )
        )
        deleted_docker_service = self.fake_docker_client.service_map.get(service_name)
        self.assertIsNone(deleted_docker_service)

    def test_archive_service_with_port(self):
        project, service = self.create_and_deploy_caddy_docker_service()

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            PortConfiguration.objects.filter(
                dockerregistryservice__slug=service.slug
            ).count(),
        )

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(
                original_id=service.id
            ).prefetch_related("ports")
        ).first()
        self.assertEqual(1, archived_service.ports.count())

        service_name = get_swarm_service_name_for_deployment(
            (
                archived_service.project.original_id,
                archived_service.original_id,
                archived_service.deployment_hashes[0],
            )
        )
        deleted_docker_service = self.fake_docker_client.service_map.get(service_name)
        self.assertIsNone(deleted_docker_service)

    def test_archive_service_with_urls(self):
        project, service = self.create_and_deploy_caddy_docker_service(
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

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            URL.objects.filter(domain="thullo.fredkiss.dev", base_path="/api").count(),
        )

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(
                original_id=service.id
            ).prefetch_related("urls")
        ).first()
        self.assertEqual(1, len(archived_service.urls.all()))

        service_name = get_swarm_service_name_for_deployment(
            (
                archived_service.project.original_id,
                archived_service.original_id,
                archived_service.deployment_hashes[0],
            )
        )
        deleted_docker_service = self.fake_docker_client.service_map.get(service_name)
        self.assertIsNone(deleted_docker_service)

    def test_archive_service_non_existing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_archive_service_for_non_existing_project(self):
        owner = self.loginUser()
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": "zane-ops", "service_slug": "cache-db"},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_archive_should_delete_monitoring_tasks_for_the_deployment(self):
        project, service = self.create_and_deploy_REDIS_docker_service()

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": project.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deployments = DockerDeployment.objects.filter(service__slug=service.slug)
        self.assertEqual(0, deployments.count())
        self.assertEqual(0, PeriodicTask.objects.count())
        self.assertEqual(0, IntervalSchedule.objects.count())


class DockerServiceMonitorTests(AuthAPITestCase):
    def test_normal_deployment_flow(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )
        token = Token.objects.get(user=owner)
        monitor_docker_service_deployment(latest_deployment.hash, token.key)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    def test_restart_is_set_after_multiple_tasks_deployments(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.latest_production_deployment

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

        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )
        token = Token.objects.get(user=owner)
        monitor_docker_service_deployment(latest_deployment.hash, token.key)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.RESTARTING,
            latest_deployment.status,
        )

    def test_succesful_restart_deploymen_flow(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.latest_production_deployment

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

        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )
        token = Token.objects.get(user=owner)
        monitor_docker_service_deployment(latest_deployment.hash, token.key)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )

    @patch("zane_api.docker_operations.sleep")
    @patch("zane_api.docker_operations.monotonic")
    def test_unsuccesful_restart_deployment_flow(self, mock_monotonic: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        mock_monotonic.side_effect = [0, 0, 0, 31]

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        latest_deployment = service.deployments.first()

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

        mock_monotonic.side_effect = [0, 0, 0, 31]

        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )
        token = Token.objects.get(user=owner)
        monitor_docker_service_deployment(latest_deployment.hash, token.key)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.UNHEALTHY,
            latest_deployment.status,
        )

    def test_service_fail_outside_of_zane_control(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment = service.latest_production_deployment

        class FakeService:
            @staticmethod
            def tasks(*args, **kwargs):
                return []

        self.fake_docker_client.services.get = lambda _id: FakeService()

        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.status,
        )
        latest_deployment.status = DockerDeployment.DeploymentStatus.HEALTHY
        latest_deployment.save()
        token = Token.objects.get(user=owner)
        monitor_docker_service_deployment(latest_deployment.hash, token.key)
        latest_deployment = service.latest_production_deployment
        self.assertEqual(
            DockerDeployment.DeploymentStatus.UNHEALTHY,
            latest_deployment.status,
        )
