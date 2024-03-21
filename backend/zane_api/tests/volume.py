from unittest.mock import patch, Mock, MagicMock

import docker.errors
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase
from .base import APITestCase
from ..models import Project, Volume
from ..services import create_docker_volume, remove_docker_volume


class FakeDockerClient:
    class FakeVolume:
        def __init__(self, parent: 'FakeDockerClient', name: str):
            self.name = name
            self.parent = parent

        def remove(self, force: bool):
            if self.parent.raise_error:
                raise docker.errors.APIError("Unknown error")
            self.parent.volume_map.pop(self.name)

    def __init__(self, raise_error: bool = False):
        self.volumes = MagicMock()
        self.containers = MagicMock()
        self.raise_error = raise_error

        self.containers.run = self.containers_run
        self.volumes.create = self.volumes_create
        self.volumes.get = self.volumes_get
        self.volume_map = {}  # type: dict[str, FakeDockerClient.FakeVolume]

    def volumes_create(self, name: str, **kwargs):
        if self.raise_error:
            raise docker.errors.APIError("Unkwown error")

        self.volume_map[name] = FakeDockerClient.FakeVolume(parent=self, name=name)

    def volumes_get(self, name: str):
        if name not in self.volume_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.volume_map[name]

    def containers_run(self, **kwargs):
        if self.raise_error:
            raise docker.errors.APIError("Unkwown error")
        return '72689062\t/data'.encode(encoding='utf-8')


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
    def test_remove_volume_successful(self, mock_fake_docker: Mock):
        volume = Volume.objects.create(
            name="postgres DB Data",
            slug="postgres-db-data",
            project=Project.objects.first()
        )
        create_docker_volume(volume)

        remove_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.volume_map))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_remove_non_existent_volume_doesnt_throw_error(self, mock_fake_docker: Mock):
        volume = Volume.objects.create(
            name="postgres DB Data",
            slug="postgres-db-data",
            project=Project.objects.first()
        )

        remove_docker_volume(volume)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.volume_map))


class VolumeGetSizeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        owner = self.loginUser()
        Project.objects.create(name="Zane Ops", slug="zane-ops", owner=owner)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_get_volume_size(self, _: Mock):
        volume = Volume.objects.create(
            name="postgres DB Data",
            slug="postgres-db-data",
            project=Project.objects.first()
        )
        response = self.client.get(reverse('zane_api:volume.size', kwargs={"slug": volume.slug}))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertIsNotNone(data.get('size'))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_non_existant_volume(self, _: Mock):
        response = self.client.get(reverse('zane_api:volume.size', kwargs={"slug": 'postgres-db-data'}))
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        data = response.json()
        self.assertTrue(isinstance(data.get('errors'), dict))
        self.assertTrue('root' in data.get('errors'))
