from unittest.mock import patch, Mock

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase, FakeDockerClient
from .base import APITestCase
from ..docker_operations import create_docker_volume, remove_docker_volume
from ..models import Project, Volume, DockerRegistryService


class DockerVolumeTests(APITestCase):
    def setUp(self):
        owner = User.objects.create_user(username="Fredkiss3", password="password")
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

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_remove_volume_successful(self, mock_fake_docker: Mock):
        service = DockerRegistryService.objects.create(
            project=Project.objects.get(slug="zane-ops")
        )
        volume = Volume.objects.create(
            name="postgres DB Data",
        )
        create_docker_volume(volume, service)

        remove_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.volume_map))

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_remove_non_existent_volume_doesnt_throw_error(
        self, mock_fake_docker: Mock
    ):
        volume = Volume.objects.create(
            name="postgres DB Data",
        )

        remove_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.volume_map))


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
