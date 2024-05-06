from unittest.mock import patch, Mock

from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase, FakeDockerClient
from ..docker_operations import (
    create_docker_volume,
    get_docker_service_resource_name,
)
from ..models import Project, Volume, DockerRegistryService


class DockerVolumeTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_create_volume_successful(self, mock_fake_docker: Mock):
        service = DockerRegistryService.objects.create(
            project=Project.objects.get(slug="zane-ops")
        )
        volume = Volume.objects.create(
            name="postgres DB Data",
        )
        create_docker_volume(volume, service)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.volume_map))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_volume_supports_absolute_path(
        self, mock_fake_docker: Mock, _: Mock
    ):
        create_service_payload = {
            "slug": "self-github",
            "image": "gitea",
            "volumes": [
                {
                    "name": "Local time",
                    "host_path": "/etc/localtime",
                    "mount_path": "/etc/localtime",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="self-github"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume: Volume = created_service.volumes.first()
        self.assertEqual("/etc/localtime", created_volume.host_path)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.volume_map))

        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        self.assertEqual(1, len(fake_service.attached_volumes))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_volume_name_is_optional(
        self, mock_fake_docker: Mock, _: Mock
    ):
        create_service_payload = {
            "slug": "self-github",
            "image": "gitea",
            "volumes": [
                {
                    "host_path": "/etc/localtime",
                    "mount_path": "/etc/localtime",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="self-github"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume: Volume = created_service.volumes.first()
        self.assertIsNotNone(created_volume.name)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_volume_only_absolute_path_for_host_path(
        self, mock_fake_docker: Mock, _: Mock
    ):
        create_service_payload = {
            "slug": "self-github",
            "image": "gitea",
            "volumes": [
                {
                    "host_path": "./etc/localtime",
                    "mount_path": "/etc/localtime",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class VolumeGetSizeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_get_volume_size(self, _: Mock):
        volume = Volume.objects.create(
            name="postgres DB Data",
        )

        response = self.client.get(
            reverse("zane_api:volume.size", kwargs={"volume_id": volume.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertIsNotNone(data.get("size"))

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_non_existant_volume(self, _: Mock):
        response = self.client.get(
            reverse("zane_api:volume.size", kwargs={"volume_id": "abcDefGh1jk"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
