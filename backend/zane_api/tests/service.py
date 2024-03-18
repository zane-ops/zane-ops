import json
from typing import Any
from unittest.mock import patch, Mock, MagicMock

import docker.errors
from django.conf import settings
from django.urls import reverse
from docker.types import EndpointSpec
from rest_framework import status

from . import AuthAPITestCase
from ..models import Project, DockerRegistryService, DockerDeployment, Volume, PortConfiguration, URL
from ..services import get_service_resource_name, get_volume_resource_name, size_in_bytes


class FakeDockerClient:
    class FakeVolume:
        def __init__(self, parent: 'FakeDockerClient', name: str, size_limit: str = None):
            self.name = name
            self.parent = parent
            self.size_limit = size_limit

        def remove(self, force: bool):
            if self.parent.raise_error:
                raise docker.errors.APIError("Unknown error")
            self.parent.volume_map.pop(self.name)

    class FakeService:
        def __init__(self, parent: 'FakeDockerClient', name: str, volumes: dict[str, str] = None,
                     env: dict[str, str] = None, endpoint: EndpointSpec = None):
            self.name = name
            self.parent = parent
            self.attached_volumes = {} if volumes is None else volumes
            self.env = {} if env is None else env
            self.endpoint = endpoint

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

    def volumes_create(self, name: str, driver_opts: dict[str, str], **kwargs):
        self.volume_map[name] = FakeDockerClient.FakeVolume(parent=self, name=name, size_limit=driver_opts.get('o'))

    def volumes_get(self, name: str):
        if name not in self.volume_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.volume_map[name]

    def services_get(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.service_map[name]

    def services_create(self, name: str, mounts: list[str], env: list[str],
                        endpoint_spec: Any,
                        networks: list[str], image: str,
                        restart_policy: Any, update_config: Any, command: str | None,
                        labels: dict[str, str]):
        volumes: dict[str, str] = {}
        for mount in mounts:
            volume_name, mount_path, _ = mount.split(":")
            volumes[volume_name] = mount_path

        envs: dict[str, str] = {}
        for var in env:
            key, value = var.split("=")
            envs[key] = value

        self.service_map[name] = FakeDockerClient.FakeService(
            parent=self,
            name=name,
            volumes=volumes,
            env=envs,
            endpoint=endpoint_spec
        )


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
                    "name": "REDIS Data volume",
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

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume = created_service.volumes.first()

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.volume_map))

        fake_service = fake_docker_client.service_map[get_service_resource_name(created_service)]
        self.assertEqual(1, len(fake_service.attached_volumes))
        self.assertIsNotNone(fake_service.attached_volumes.get(get_volume_resource_name(created_volume)))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_volume_and_size_limit(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "cache db",
            "image": "redis:alpine",
            "volumes": [
                {
                    "name": "redis_data_volume",
                    "mount_path": "/data",
                    "size": {
                        "n": 500,
                        "unit": "MB"
                    },
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="cache-db").first()
        volume: Volume = created_service.volumes.first()

        self.assertEqual(size_in_bytes(500, 'MB'), volume.size_limit)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_volume = list(fake_docker_client.volume_map.values())[0]
        self.assertIsNotNone(fake_volume.size_limit)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_env_and_command(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "cache db",
            "image": "redis:alpine",
            "command": "redis-server --requirepass ${REDIS_PASSWORD}",
            "env": {
                "REDIS_PASSWORD": "strongPassword123"
            },
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="cache-db").first()
        env = created_service.env_variables.first()

        self.assertIsNotNone(created_service.command)
        self.assertIsNotNone(env)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[get_service_resource_name(created_service)]
        self.assertEqual(1, len(fake_service.env))
        self.assertEqual("strongPassword123", fake_service.env.get("REDIS_PASSWORD"))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_port(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "noSQL db",
            "image": "redis:alpine",
            "ports": [
                {
                    "public": 6383,
                    "forwarded": 6379
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="nosql-db").first()
        port: PortConfiguration = created_service.port_config.first()

        self.assertIsNotNone(port)
        self.assertEqual(6383, port.host)
        self.assertEqual(6379, port.forwarded)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[get_service_resource_name(created_service)]

        self.assertIsNotNone(fake_service.endpoint)

        port_in_docker = fake_service.endpoint.get('Ports')[0]
        self.assertEqual(6383, port_in_docker["PublishedPort"])
        self.assertEqual(6379, port_in_docker["TargetPort"])

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_http_port(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "Adminer UI",
            "image": "adminer:latest",
            "ports": [
                {
                    "forwarded": 8080
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="adminer-ui").first()
        port: PortConfiguration = created_service.port_config.first()

        self.assertIsNotNone(port)
        self.assertIsNone(port.host)
        self.assertEqual(8080, port.forwarded)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[get_service_resource_name(created_service)]

        self.assertIsNone(fake_service.endpoint)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_port_create_a_domain(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "Adminer UI",
            "image": "adminer:latest",
            "ports": [
                {
                    "forwarded": 8080
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="adminer-ui").first()

        default_url: URL = created_service.urls.first()
        self.assertIsNotNone(default_url)
        self.assertEqual(f"{p.slug}-{created_service.slug}.{settings.ROOT_DOMAIN}", default_url.domain)
        self.assertEqual("/", default_url.base_path)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_explicit_domain(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "Portainer UI",
            "image": "portainer/portainer-ce:latest",
            "urls": [
                {
                    "domain": "dcr.fredkiss.dev",
                    "base_path": "/portainer"
                }
            ],
            "ports": [
                {
                    "forwarded": 8000
                }
            ]
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="portainer-ui").first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("dcr.fredkiss.dev", url.domain)
        self.assertEqual("/portainer", url.base_path)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_without_port_does_not_create_a_domain(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "Main Database",
            "image": "postgres:12-alpine",
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="main-database").first()
        self.assertEqual(0, created_service.urls.count())

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_with_no_http_public_port_does_not_create_a_domain(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "Main Database",
            "image": "postgres:12-alpine",
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=json.dumps(create_redis_payload),
            content_type='application/json'
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="main-database").first()
        self.assertIsNone(created_service.base_domain)
        port: PortConfiguration = created_service.port_config.first()

        self.assertIsNone(port)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[get_service_resource_name(created_service)]

        self.assertIsNone(fake_service.endpoint)

    # @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    # def test_create_redis_service(self, mock_fake_docker: Mock):
    #     owner = self.loginUser()
    #     p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)
    #
    #     create_redis_payload = {
    #         "name": "cache db",
    #         "image": "redis:alpine",
    #         "command": "redis-server --requirepass ${REDIS_PASSWORD}",
    #         "env": {
    #             "REDIS_PASSWORD": "strongPassword123"
    #         },
    #         "volumes": [
    #             {
    #                 "name": "redis_data_volume",
    #                 "size": {
    #                     "n": 1,
    #                     "unit": "MB"
    #                 },
    #                 "mount_path": "/data"
    #             }
    #         ]
    #     }
    #
    #     response = self.client.post(
    #         reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
    #         data=create_redis_payload
    #     )
    #     self.assertEqual(status.HTTP_201_CREATED, response.status_code)
    #
    #     created_service: DockerRegistryService = DockerRegistryService.objects.filter(slug="cache-db").first()
    #     self.assertIsNotNone(created_service)
    #     self.assertEqual(1, len(created_service.env_variables.count()))
    #     self.assertEqual(1, len(created_service.volumes.count()))
    #
    #     fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
    #
    #     self.assertEqual(1, len(fake_docker_client.volume_map))
    #     self.assertEqual(1, len(fake_docker_client.service_map))
