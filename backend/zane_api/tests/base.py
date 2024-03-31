from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import docker.errors
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from docker.types import EndpointSpec
from rest_framework.test import APIClient

from ..docker_operations import get_network_resource_name
from ..models import Project


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    DEBUG=True,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_BROKER_URL="memory://",
    CELERY_TASK_STORE_EAGER_RESULT=True,
)
class APITestCase(TestCase):
    client = APIClient(enforce_csrf_checks=True, content_type="application/json")

    def tearDown(self):
        cache.clear()


class AuthAPITestCase(APITestCase):
    def setUp(self):
        User.objects.create_user(username="Fredkiss3", password="password")

    def loginUser(self):
        self.client.login(username="Fredkiss3", password="password")
        return User.objects.get(username="Fredkiss3")


class FakeDockerClient:
    @dataclass
    class FakeNetwork:
        name: str
        id: str
        parent: "FakeDockerClient"

        def remove(self):
            self.parent.network_remove(self.name)

    class FakeVolume:
        def __init__(self, parent: "FakeDockerClient", name: str, labels: dict = None):
            self.name = name
            self.parent = parent
            self.labels = labels if labels is not None else {}

        def remove(self, force: bool):
            self.parent.volume_map.pop(self.name)

    class FakeService:
        def __init__(
            self,
            parent: "FakeDockerClient",
            name: str,
            volumes: dict[str, str] = None,
            env: dict[str, str] = None,
            endpoint: EndpointSpec = None,
        ):
            self.attrs = {
                "Spec": {
                    "TaskTemplate": {
                        "Networks": [],
                    },
                }
            }
            self.name = name
            self.parent = parent
            self.attached_volumes = {} if volumes is None else volumes
            self.env = {} if env is None else env
            self.endpoint = endpoint

        def remove(self):
            self.parent.services_remove(self.name)

        def update(self, networks: list):
            self.attrs["Spec"]["TaskTemplate"]["Networks"] = [
                {"Target": network} for network in networks
            ]

    PORT_USED_BY_HOST = 8080

    def __init__(self):
        self.volumes = MagicMock()
        self.services = MagicMock()
        self.images = MagicMock()
        self.containers = MagicMock()
        self.is_logged_in = False
        self.credentials = {}

        self.containers.run = self.containers_run
        self.images.get_registry_data = self.image_get_registry_data
        self.services.create = self.services_create
        self.services.get = self.services_get
        self.volumes.create = self.volumes_create
        self.volumes.get = self.volumes_get
        self.volumes.list = self.volumes_list
        self.volume_map = {}  # type: dict[str, FakeDockerClient.FakeVolume]
        self.service_map = {
            settings.CADDY_PROXY_SERVICE: FakeDockerClient.FakeService(
                name="zane_zane-proxy", parent=self
            )
        }  # type: dict[str, FakeDockerClient.FakeService]

        self.networks = MagicMock()
        self.network_map = {}  # type: dict[str, FakeDockerClient.FakeNetwork]

        self.networks.create = self.docker_create_network
        self.networks.get = self.docker_get_network

    def containers_run(
        self, image: str, ports: dict[str, tuple[str, int]], command: str, remove: bool
    ):
        _, port = list(ports.values())[0]
        if port == self.PORT_USED_BY_HOST:
            raise docker.errors.APIError(f"Port {port} is already used")

    def volumes_create(self, name: str, labels: dict, **kwargs):
        self.volume_map[name] = FakeDockerClient.FakeVolume(
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
            raise docker.errors.NotFound("Service Not found")
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

        self.service_map[name] = FakeDockerClient.FakeService(
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

    def docker_create_network(self, name: str, **kwargs):
        created_network = FakeDockerClient.FakeNetwork(name=name, id=name, parent=self)
        self.network_map[name] = created_network
        return created_network

    def docker_get_network(self, name: str):
        network = self.network_map.get(name)

        if network is None:
            raise docker.errors.NotFound("network not found")
        return network

    def network_remove(self, name: str):
        network = self.network_map.pop(name)
        if network is None:
            raise docker.errors.NotFound("network not found")

    def get_network(self, p: Project):
        return self.network_map.get(get_network_resource_name(p.id))

    def create_network(self, p: Project):
        return self.docker_create_network(
            get_network_resource_name(p.id),
            scope="swarm",
            driver="overlay",
        )

    def get_networks(self):
        return self.network_map
