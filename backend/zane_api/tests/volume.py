from unittest.mock import patch, Mock, MagicMock

import docker.errors
from django.contrib.auth.models import User

from .base import APITestCase
from ..models import Project, Volume
from ..services import create_docker_volume


class FakeDockerClient:
    class FakeVolume:
        def __init__(self, parent: 'FakeDockerClient', name: str, size_limit: str = None):
            self.name = name
            self.parent = parent
            self.size_limit = size_limit

    def __init__(self, raise_error: bool = False):
        self.volumes = MagicMock()
        self.raise_error = raise_error

        self.volumes.create = self.volumes_create
        self.volume_map = {}  # type: dict[str, FakeDockerClient.FakeVolume]

    def volumes_create(self, name: str, driver_opts: dict[str, str], **kwargs):
        if self.raise_error:
            raise docker.errors.APIError("Unkwown error")

        self.volume_map[name] = FakeDockerClient.FakeVolume(parent=self, name=name, size_limit=driver_opts.get('o'))


class DockerVolumeTests(APITestCase):
    def setUp(self):
        owner = User.objects.create_user(username="Fredkiss3", password="password")
        Project.objects.create(name="Zane Ops", slug="zane-ops", owner=owner)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_volume_successful(self, mock_fake_docker: Mock):
        volume = Volume.objects.create(name="postgres DB Data", slug="postgres-db-data",
                                       project=Project.objects.first())
        create_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.volume_map))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_volume_with_size_limit(self, mock_fake_docker: Mock):
        one_gigabyte = 1 * 1024 ** 3
        volume = Volume.objects.create(
            name="postgres DB Data",
            slug="postgres-db-data",
            project=Project.objects.first(),
            size_limit=one_gigabyte
        )
        create_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        volume = list(fake_docker_client.volume_map.values())[0]
        self.assertIsNotNone(volume.size_limit)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_volume_without_size_limit(self, mock_fake_docker: Mock):
        volume = Volume.objects.create(
            name="postgres DB Data",
            slug="postgres-db-data",
            project=Project.objects.first()
        )
        create_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        volume = list(fake_docker_client.volume_map.values())[0]
        self.assertIsNone(volume.size_limit)
