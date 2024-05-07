from unittest.mock import Mock, patch, MagicMock

from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase, FakeDockerClient
from ..models import Project, DockerDeployment


class DockerServiceDeploymentViewTests(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_deployments_succesful(self, mock_fake_docker: Mock):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_filter_deployments_succesful(self, mock_fake_docker: Mock):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                },
            )
            + "?deployment_status=OFFLINE"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(0, len(data))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_deployments_project_non_existing(self, mock_fake_docker: Mock):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": "inexistent",
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_deployments_service_non_existing(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_single_deployment_succesful(self, mock_fake_docker: Mock):
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
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_single",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                    "deployment_hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_single_deployment_service_non_existing(self, mock_fake_docker: Mock):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_single",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                    "deployment_hash": "dkr_dpl_hash1234",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_use_specific_tag_for_deployment_with_the_user_specifed_one(
        self, mock_fake_docker: Mock, _: Mock
    ):
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
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertEqual("alpine", deployment.image_tag)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_use_latest_tag_for_deployment_when_no_tag_specifed(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertEqual("latest", deployment.image_tag)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_add_deployment_url_when_url_is_provided(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "webserver",
            "image": "caddy",
            "urls": [{"domain": "caddy.zaneops.dev"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="webserver"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNotNone(deployment.url)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_add_deployment_url_when_port_is_provided(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "webserver",
            "image": "caddy",
            "ports": [{"forwarded": "80"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="webserver"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNotNone(deployment.url)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_do_not_add_deployment_url_when_no_port_or_url_is_provided(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNone(deployment.url)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_mark_deployment_as_failed_when_the_task_fails(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
        }

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        exception = Exception("unexpected exception")

        def create_raise_error(*args, **kwargs):
            raise exception

        fake_docker_client.services.create = create_raise_error

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED, deployment.deployment_status
        )
        self.assertEqual(str(exception), deployment.deployment_status_reason)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_scale_down_the_service_for_the_deployment_when_the_task_fails(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
        }

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        exception = Exception("unexpected exception")

        def create_raise_error(*args, **kwargs):
            raise exception

        fake_service = MagicMock()
        fake_docker_client.services.create = create_raise_error
        fake_docker_client.services.list = lambda *args, **kwargs: [fake_service]

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED, deployment.deployment_status
        )
        self.assertEqual(str(exception), deployment.deployment_status_reason)
        fake_service.scale.assert_called_with(0)
