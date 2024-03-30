import json
import random
from typing import Any
from unittest.mock import patch, Mock, MagicMock

import docker.errors
from django.conf import settings
from django.urls import reverse
from docker.types import EndpointSpec
from rest_framework import status

from . import AuthAPITestCase
from ..docker_operations import (
    get_docker_service_resource_name,
    get_volume_resource_name,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    PortConfiguration,
    URL,
    ArchivedDockerService,
    DockerEnvVariable,
)


class FakeDockerClientWithServices:
    class FakeVolume:
        def __init__(
            self, parent: "FakeDockerClientWithServices", name: str, labels: dict = None
        ):
            self.name = name
            self.parent = parent
            self.labels = labels if labels is not None else {}

        def remove(self, force: bool):
            if self.parent.raise_error:
                raise docker.errors.APIError("Unknown error")
            self.parent.volume_map.pop(self.name)

    class FakeService:
        def __init__(
            self,
            parent: "FakeDockerClientWithServices",
            name: str,
            volumes: dict[str, str] = None,
            env: dict[str, str] = None,
            endpoint: EndpointSpec = None,
        ):
            self.name = name
            self.parent = parent
            self.attached_volumes = {} if volumes is None else volumes
            self.env = {} if env is None else env
            self.endpoint = endpoint

        def remove(self):
            self.parent.services_remove(self.name)

    def __init__(self, raise_error: bool = False):
        self.volumes = MagicMock()
        self.services = MagicMock()
        self.images = MagicMock()
        self.containers = MagicMock()
        self.raise_error = raise_error
        self.is_logged_in = False
        self.credentials = {}

        self.containers.run = self.containers_run
        self.images.get_registry_data = self.image_get_registry_data
        self.services.create = self.services_create
        self.services.get = self.services_get
        self.volumes.create = self.volumes_create
        self.volumes.get = self.volumes_get
        self.volumes.list = self.volumes_list
        self.volume_map = {}  # type: dict[str, FakeDockerClientWithServices.FakeVolume]
        self.service_map = (
            {}
        )  # type: dict[str, FakeDockerClientWithServices.FakeService]

    @staticmethod
    def containers_run(
        image: str, ports: dict[str, tuple[str, int]], command: str, remove: bool
    ):
        _, port = list(ports.values())[0]
        if port == 8080:
            raise docker.errors.APIError(f"Port {port} is already used")

    def volumes_create(self, name: str, labels: dict, **kwargs):
        self.volume_map[name] = FakeDockerClientWithServices.FakeVolume(
            parent=self, name=name, labels=labels
        )

    def volumes_get(self, name: str):
        if name not in self.volume_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.volume_map[name]

    def volumes_list(self, labels: dict):
        return [
            volume for volume in self.volume_map.values() if volume.labels == labels
        ]

    def services_get(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.service_map[name]

    def services_remove(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound("Volume Not found")
        self.service_map.pop(name)

    def services_create(
        self,
        name: str,
        mounts: list[str],
        env: list[str],
        endpoint_spec: Any,
        networks: list[str],
        image: str,
        restart_policy: Any,
        update_config: Any,
        command: str | None,
        labels: dict[str, str],
    ):
        volumes: dict[str, str] = {}
        for mount in mounts:
            volume_name, mount_path, _ = mount.split(":")
            if volume_name not in self.volume_map:
                raise docker.errors.NotFound("Volume not created")
            volumes[volume_name] = mount_path

        envs: dict[str, str] = {}
        for var in env:
            key, value = var.split("=")
            envs[key] = value

        self.service_map[name] = FakeDockerClientWithServices.FakeService(
            parent=self, name=name, volumes=volumes, env=envs, endpoint=endpoint_spec
        )

    def login(self, username: str, password: str, registry: str, **kwargs):
        if (
            username != "fredkiss3"
            or password != "s3cret"
            or registry != "https://dcr.fredkiss.dev/"
        ):
            raise docker.errors.APIError("Bad Credentials")
        self.credentials = dict(username=username, password=password)
        self.is_logged_in = True

    def image_get_registry_data(self, image: str, auth_config: dict):
        if auth_config is not None:
            if not image.startswith("dcr.fredkiss.dev"):
                raise docker.errors.APIError("Invalid credentials")

            if not image.startswith("dcr.fredkiss.dev/gh-next"):
                raise docker.errors.NotFound("This image does not exist")
        else:
            if image == "nonexistent":
                raise docker.errors.ImageNotFound("This image does not exist")


class DockerServiceCreateViewTest(AuthAPITestCase):

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_simple_service(self, mock_fake_docker: Mock, _: Mock):
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
        data = response.json().get("service")
        self.assertIsNotNone(data)

        created_service = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)
        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.service_map))

        deployment = DockerDeployment.objects.filter(service=created_service).first()
        self.assertIsNotNone(deployment)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_volume(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "volumes": [{"name": "REDIS Data volume", "mount_path": "/data"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume = created_service.volumes.first()

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.volume_map))

        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        self.assertEqual(1, len(fake_service.attached_volumes))
        self.assertIsNotNone(
            fake_service.attached_volumes.get(get_volume_resource_name(created_volume))
        )

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_env_and_command(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "command": "redis-server --requirepass ${REDIS_PASSWORD}",
            "env": {"REDIS_PASSWORD": "strongPassword123"},
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        env = created_service.env_variables.first()

        self.assertIsNotNone(created_service.command)
        self.assertIsNotNone(env)

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        self.assertEqual(1, len(fake_service.env))
        self.assertEqual("strongPassword123", fake_service.env.get("REDIS_PASSWORD"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_port(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "nosql-db",
            "image": "redis:alpine",
            "ports": [{"public": 6383, "forwarded": 6379}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="nosql-db"
        ).first()
        port: PortConfiguration = created_service.ports.first()

        self.assertIsNotNone(port)
        self.assertEqual(6383, port.host)
        self.assertEqual(6379, port.forwarded)

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]

        self.assertIsNotNone(fake_service.endpoint)

        port_in_docker = fake_service.endpoint.get("Ports")[0]
        self.assertEqual(6383, port_in_docker["PublishedPort"])
        self.assertEqual(6379, port_in_docker["TargetPort"])

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_should_not_work_with_unavailable_host_port(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "nosql-db",
            "image": "redis:alpine",
            "ports": [
                {"public": 8080, "forwarded": 6379},
                {"public": 8085, "forwarded": 6379},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("ports"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="nosql-db"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_should_not_work_with_port_already_used_by_other_services(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            slug="cache-db", image="redis:alpine", project=p
        )

        used_port = PortConfiguration(
            host=8082,
            forwarded=5540,
        )
        used_port.save()
        service.ports.add(used_port)

        create_service_payload = {
            "slug": "adminer",
            "image": "adminer:latest",
            "ports": [{"public": used_port.host, "forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("ports"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_http_port(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()
        port: PortConfiguration = created_service.ports.first()

        self.assertIsNotNone(port)
        self.assertIsNone(port.host)
        self.assertEqual(8080, port.forwarded)

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]

        self.assertIsNone(fake_service.endpoint)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_port_create_a_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()

        default_url: URL = created_service.urls.first()
        self.assertIsNotNone(default_url)
        self.assertEqual(
            f"{p.slug}-{created_service.slug}.{settings.ROOT_DOMAIN}",
            default_url.domain,
        )
        self.assertEqual("/", default_url.base_path)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_explicit_domain(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "portainer-ui",
            "image": "portainer/portainer-ce:latest",
            "urls": [{"domain": "dcr.fredkiss.dev", "base_path": "/portainer"}],
            "ports": [{"forwarded": 8000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="portainer-ui"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("dcr.fredkiss.dev", url.domain)
        self.assertEqual("/portainer", url.base_path)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_explicit_domain_and_strip_prefix(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "portainer-ui",
            "image": "portainer/portainer-ce:latest",
            "urls": [
                {
                    "domain": "dcr.fredkiss.dev",
                    "base_path": "/portainer",
                    "strip_prefix": False,
                }
            ],
            "ports": [{"forwarded": 8000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="portainer-ui"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("dcr.fredkiss.dev", url.domain)
        self.assertEqual("/portainer", url.base_path)
        self.assertEqual(False, url.strip_prefix)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_without_port_does_not_create_a_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "main-database",
            "image": "postgres:12-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-database"
        ).first()
        self.assertEqual(0, created_service.urls.count())

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_no_http_public_port_does_not_create_a_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "public-database",
            "image": "postgres:12-alpine",
            "ports": [{"public": 5433, "forwarded": 5432}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="public-database"
        ).first()

        self.assertEqual(0, created_service.urls.count())

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_create_a_domain_if_public_port_is_80_or_443(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"public": random.choice([443, 80]), "forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()
        self.assertEqual(1, created_service.urls.count())

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_can_only_specify_one_http_port(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [
                {"public": 443, "forwarded": 8080},
                {"public": 80, "forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("ports"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_cannot_specify_the_same_public_port_twice(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [
                {"public": 8080, "forwarded": 8080},
                {"public": 8080, "forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("ports"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_cannot_specify_the_same_url_twice(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "urls": [
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
            ],
            "ports": [
                {"forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("urls"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_cannot_specify_the_same_volume_mount_path_twice(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "gitea",
            "image": "gitea/gitea:latest",
            "volumes": [
                {"name": "gitea data", "mount_path": "/data"},
                {"name": "gitea config", "mount_path": "/data"},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("volumes"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_cannot_create_service_with_zane_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "urls": [
                {"domain": settings.ZANE_APP_DOMAIN},
            ],
            "ports": [
                {"forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("urls"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_cannot_specify_custom_url_and_public_port_at_the_same_time(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "portainer-ce:latest",
            "urls": [
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
            ],
            "ports": [
                {"public": 8099, "forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("urls"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_create_implicit_port_if_custom_url_is_specified(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "portainer-ce:latest",
            "urls": [
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        self.assertEqual(1, created_service.ports.count())
        create_port: PortConfiguration = created_service.ports.first()
        self.assertEqual(80, create_port.forwarded)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_custom_registry(self, mock_fake_docker: Mock, _: Mock):
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
        self.assertEqual("fredkiss3", created_service.docker_credentials_username)
        self.assertEqual("s3cret", created_service.docker_credentials_password)

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value

        self.assertTrue(fake_docker_client.is_logged_in)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_custom_registry_does_not_create_service_if_bad_image_credentials(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "bad",
                "registry_url": "https://dcr.fredkiss.dev/",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("credentials"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_custom_registry_does_not_create_service_if_nonexistent_image(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()

        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/nonexistent:latest",
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
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("image"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertTrue(fake_docker_client.is_logged_in)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_credentials_do_not_correspond_to_image(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "gcr.io/redis:latest",
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
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("image"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_service_if_nonexistent_dockerhub_image(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "nonexistent",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("image"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_bad_request(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json().get("errors")
        self.assertIsNotNone(errors)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_for_nonexistent_project(
        self, mock_fake_docker: Mock, _: Mock
    ):
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

        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("root"))

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_conflict_with_slug(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        DockerRegistryService.objects.create(
            slug="cache-db", image="redis:alpine", project=p
        )

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

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("slug"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_with_urls_already_used_by_other_services(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        existing_service = DockerRegistryService.objects.create(
            slug="redis", image="redis:alpine", project=p
        )
        url = URL.objects.bulk_create(
            [
                URL(domain="thullo.zane.local", base_path="/"),
            ]
        )
        existing_service.urls.add(*url)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "urls": [{"domain": "thullo.zane.local"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        errors = response.json()["errors"]
        self.assertIsNotNone(errors.get("urls"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_slug_is_created_if_not_specified(
        self, mock_fake_docker: Mock, _: Mock
    ):
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

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_create_service_slug_is_lowercased(self, mock_fake_docker: Mock, _: Mock):
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


class DockerGetServiceViewTest(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_get_service_succesful(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            slug="cache-db", image="redis:alpine", project=p
        )

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json().get("service")
        self.assertIsNotNone(data)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_get_service_non_existing(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("root"))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_get_service_not_in_the_correct_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p1 = Project.objects.create(slug="kiss-cam", owner=owner)
        p2 = Project.objects.create(slug="camly", owner=owner)

        service = DockerRegistryService.objects.create(
            slug="cache-db", image="redis:alpine", project=p1
        )

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p2.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("root"))


class DockerServiceArchiveViewTest(AuthAPITestCase):
    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_simple_service(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = ArchivedDockerService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(archived_service)

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.service_map))

        deployments = DockerDeployment.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deployments))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_service_with_volume(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "volumes": [{"name": "REDIS Data volume", "mount_path": "/data"}],
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="cache-db").prefetch_related(
                "volumes"
            )
        ).first()
        self.assertEqual(1, len(archived_service.volumes.all()))

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.service_map))
        self.assertEqual(0, len(fake_docker_client.volume_map))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_service_with_env_and_command(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "command": "redis-server --requirepass ${REDIS_PASSWORD}",
            "env": {"REDIS_PASSWORD": "strongPassword123"},
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_envs = DockerEnvVariable.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deleted_envs))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="cache-db").prefetch_related(
                "env_variables"
            )
        ).first()
        self.assertEqual(1, len(archived_service.env_variables.all()))

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.service_map))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_service_with_port(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "ports": [{"public": 6383, "forwarded": 6379}],
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_ports = PortConfiguration.objects.filter(host=6383)
        self.assertEqual(0, len(deleted_ports))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="cache-db").prefetch_related(
                "ports"
            )
        ).first()
        self.assertEqual(1, len(archived_service.ports.all()))

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.service_map))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_service_with_urls(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="thullo", owner=owner)

        create_service_payload = {
            "slug": "thullo-api",
            "image": "dcr.fredkiss.dev/thullo-api:latest",
            "urls": [{"domain": "thullo.fredkiss.dev", "base_path": "/api"}],
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "thullo-api"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_urls = URL.objects.filter(
            domain="thullo.fredkiss.dev", base_path="/api"
        )
        self.assertEqual(0, len(deleted_urls))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="thullo-api").prefetch_related(
                "urls"
            )
        ).first()
        self.assertEqual(1, len(archived_service.urls.all()))

        fake_docker_client: FakeDockerClientWithServices = mock_fake_docker.return_value
        self.assertEqual(0, len(fake_docker_client.service_map))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_service_non_existing(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("root"))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithServices(),
    )
    def test_archive_service_for_non_existing_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": "zane-ops", "service_slug": "cache-db"},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        errors = response.json().get("errors")
        self.assertIsNotNone(errors)
        self.assertIsNotNone(errors.get("root"))
