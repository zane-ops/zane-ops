import json
from unittest.mock import patch, Mock, MagicMock

import docker.errors
from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase
from ..models import Project, DockerRegistryService, DockerDeployment


class FakeDockerClient:
    class FakeVolume:
        def __init__(self, parent: 'FakeDockerClient', name: str):
            self.name = name
            self.parent = parent

        def remove(self, force: bool):
            if self.parent.raise_error:
                raise docker.errors.APIError("Unknown error")
            self.parent.volume_map.pop(self.name)

    class FakeService:
        def __init__(self, parent: 'FakeDockerClient', name: str):
            self.name = name
            self.parent = parent
            # self.volumes = 

    def __init__(self, raise_error: bool = False):
        self.volumes = MagicMock()
        self.services = MagicMock()
        self.raise_error = raise_error

        self.services.create = self.services_create
        self.services.get = self.services_get
        self.volumes.create = self.volumes_create
        self.volumes.get = self.volumes_get
        self.volume_map = {}  # type: dict[str, FakeDockerClient.FakeVolume]
        self.service_map = {}  # type: dict[str, FakeDockerClient.FakeService]

    def volumes_create(self, name: str, **kwargs):
        self.volume_map[name] = FakeDockerClient.FakeVolume(parent=self, name=name)

    def volumes_get(self, name: str):
        if name not in self.volume_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.volume_map[name]

    def services_get(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.service_map[name]

    def services_create(self, name: str, **kwargs):
        self.service_map[name] = FakeDockerClient.FakeService(parent=self, name=name)


class DockerServiceCreateViewTest(AuthAPITestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_simple_service(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "cache db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=create_redis_payload
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.service_map))

        deployment = DockerDeployment.objects.filter(service=created_service).first()
        self.assertIsNotNone(deployment)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_volume(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "cache db",
            "image": "redis:alpine",
            "volumes": [
                {
                    "name": "redis_data_volume",
                    "mount_path": "/data"
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.volume_map))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_redis_service(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "cache db",
            "image": "redis:alpine",
            "command": "redis-server --requirepass ${REDIS_PASSWORD}",
            "env": {
                "REDIS_PASSWORD": "strongPassword123"
            },
            "volumes": [
                {
                    "name": "redis_data_volume",
                    "size": {
                        "n": 1,
                        "unit": "MB"
                    },
                    "mount_path": "/data"
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=create_redis_payload
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, len(created_service.env_variables))
        self.assertEqual(1, len(created_service.volumes))

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        self.assertEqual(1, len(fake_docker_client.volume_map))
        self.assertEqual(1, len(fake_docker_client.service_map))
