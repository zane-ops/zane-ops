import json
from dataclasses import dataclass
from typing import List
from unittest.mock import MagicMock, patch

import docker.errors
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from docker.types import EndpointSpec
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..docker_operations import get_network_resource_name, DockerImageResultFromRegistry
from ..models import Project, DockerDeploymentChange, DockerRegistryService


class CustomAPIClient(APIClient):
    def __init__(self, parent: TestCase, **defaults):
        super().__init__(enforce_csrf_checks=False, **defaults)
        self.parent = parent

    def post(
        self, path, data=None, format=None, content_type=None, follow=False, **extra
    ):
        if type(data) is dict:
            data = json.dumps(data)

        with self.parent.captureOnCommitCallbacks(execute=True) as callbacks:
            response = super().post(
                path=path,
                data=data,
                format=format,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
            )
        return response

    def put(
        self, path, data=None, format=None, content_type=None, follow=False, **extra
    ):
        if type(data) is dict:
            data = json.dumps(data)
        with self.parent.captureOnCommitCallbacks(execute=True):
            response = super().put(
                path=path,
                data=data,
                format=format,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
            )
        return response

    def patch(
        self, path, data=None, format=None, content_type=None, follow=False, **extra
    ):
        if type(data) is dict:
            data = json.dumps(data)
        with self.parent.captureOnCommitCallbacks(execute=True):
            response = super().patch(
                path=path,
                data=data,
                format=format,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
            )
        return response

    def delete(
        self, path, data=None, format=None, content_type=None, follow=False, **extra
    ):
        if type(data) == dict:
            data = json.dumps(data)
        with self.parent.captureOnCommitCallbacks(execute=True):
            response = super().delete(
                path=path,
                data=data,
                format=format,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
            )
        return response


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    # DEBUG=True,  # uncomment for debugging celery tasks
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_BROKER_URL="memory://",
    CELERY_TASK_STORE_EAGER_RESULT=True,
)
class APITestCase(TestCase):
    def setUp(self):
        self.client = CustomAPIClient(parent=self)
        self.fake_docker_client = FakeDockerClient()

        # these functions are always patched
        patch("zane_api.tasks.expose_docker_service_to_http").start()
        patch("zane_api.tasks.unexpose_docker_service_from_http").start()
        patch("zane_api.tasks.expose_docker_service_deployment_to_http").start()
        patch(
            "zane_api.docker_operations.get_docker_client",
            return_value=self.fake_docker_client,
        ).start()

        self.addCleanup(patch.stopall)

    def tearDown(self):
        cache.clear()

    def assertDictContainsSubset(self, subset: dict, parent: dict, msg: object = None):
        extracted_subset = dict(
            [(key, parent[key]) for key in subset.keys() if key in parent.keys()]
        )
        self.assertEqual(subset, extracted_subset, msg)


class AuthAPITestCase(APITestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username="Fredkiss3", password="password")

    def loginUser(self):
        self.client.login(username="Fredkiss3", password="password")
        user = User.objects.get(username="Fredkiss3")
        Token.objects.get_or_create(user=user)
        return user

    def create_and_deploy_redis_docker_service(
        self,
        with_healthcheck: bool = False,
        other_changes: list[DockerDeploymentChange] = None,
    ):
        owner = self.loginUser()
        project = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=project)

        other_changes = other_changes if other_changes is not None else []
        if with_healthcheck:
            other_changes.append(
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "valkey-cli validate",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                    },
                    service=service,
                ),
            )

        for change in other_changes:
            change.service = service
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.2-alpine",
                    service=service,
                ),
            ]
            + other_changes
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return project, service

    def create_and_deploy_caddy_docker_service(
        self,
        with_healthcheck: bool = False,
        other_changes: list[DockerDeploymentChange] = None,
    ):
        owner = self.loginUser()
        project = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=project)

        other_changes = other_changes if other_changes is not None else []
        if with_healthcheck:
            other_changes.append(
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                    },
                    service=service,
                ),
            )

        for change in other_changes:
            change.service = service
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
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
            ]
            + other_changes
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return project, service


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
            volumes: dict[str, dict[str, str]] = None,
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
            self.id = name
            self.swarm_tasks = [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "DesiredState": "running",
                }
            ]

        def remove(self):
            self.parent.services_remove(self.name)

        def update(self, networks: list):
            self.attrs["Spec"]["TaskTemplate"]["Networks"] = [
                {"Target": network} for network in networks
            ]

        def tasks(self, *args, **kwargs):
            return self.swarm_tasks

        def scale(self, replicas: int):
            """do nothing for now"""
            if replicas == 0:
                self.swarm_tasks = []

    class FakeContainer:
        @staticmethod
        def exec_run(cmd: str, *args, **kwargs):
            if cmd == FakeDockerClient.FAILING_CMD:
                return 1, b"connection refused"
            return 0, b"connection succesful"

    PORT_USED_BY_HOST = 8080
    FAILING_CMD = "invalid"
    NONEXISTANT_IMAGE = "nonexistant"
    NONEXISTANT_PRIVATE_IMAGE = "example.com/nonexistant"

    def __init__(self):
        self.volumes = MagicMock()
        self.services = MagicMock()
        self.images = MagicMock()
        self.containers = MagicMock()
        self.is_logged_in = False
        self.credentials = {}

        self.images.search = self.images_search
        self.images.pull = self.images_pull
        self.containers.run = self.containers_run
        self.containers.get = self.containers_get
        self.images.get_registry_data = self.image_get_registry_data
        self.services.create = self.services_create
        self.services.get = self.services_get
        self.services.list = self.services_list
        self.volumes.create = self.volumes_create
        self.volumes.get = self.volumes_get
        self.volumes.list = self.volumes_list

        self.networks = MagicMock()
        self.network_map = {}  # type: dict[str, FakeDockerClient.FakeNetwork]

        self.networks.create = self.docker_create_network
        self.networks.get = self.docker_get_network

        self.volume_map = {}  # type: dict[str, FakeDockerClient.FakeVolume]
        self.service_map = {
            "proxy-service": FakeDockerClient.FakeService(
                name="zane_zane-proxy", parent=self
            )
        }  # type: dict[str, FakeDockerClient.FakeService]
        self.pulled_images: set[str] = set()

    def services_list(self, **kwargs):
        if kwargs.get("filter") == {"label": "zane.role=proxy"}:
            return [self.service_map["proxy_service"]]
        return [service for service in self.service_map.values()]

    def events(self, decode: bool, filters: dict):
        return []

    def containers_get(self, container_id: str):
        return FakeDockerClient.FakeContainer()

    def containers_run(self, command: str, *args, **kwargs):
        ports: dict[str, tuple[str, int]] = kwargs.get("ports")
        if ports is not None:
            _, port = list(ports.values())[0]
            if port == self.PORT_USED_BY_HOST:
                raise docker.errors.APIError(f"Port {port} is already used")
        if command == "du -sb /data":
            return "72689062\t/data".encode(encoding="utf-8")

    def volumes_create(self, name: str, labels: dict, **kwargs):
        self.volume_map[name] = FakeDockerClient.FakeVolume(
            parent=self, name=name, labels=labels
        )

    def volumes_get(self, name: str):
        if name not in self.volume_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.volume_map[name]

    def volumes_list(self, filters: dict):
        label_in_filters: list[str] = filters.get("label", [])
        labels = {}
        for label in label_in_filters:
            key, value = label.split("=")
            labels[key] = value
        return [
            volume for volume in self.volume_map.values() if volume.labels == labels
        ]

    def services_get(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound(f"Service with `{name=}` Not found")
        return self.service_map[name]

    def services_remove(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound("Service Not found")
        self.service_map.pop(name)

    def services_create(
        self,
        name: str,
        *args,
        **kwargs,
    ):
        image: str | None = kwargs.get("image", None)
        mounts: list[str] = kwargs.get("mounts", [])
        env: list[str] = kwargs.get("env", [])
        endpoint_spec = kwargs.get("endpoint_spec", None)
        if image not in self.pulled_images:
            raise docker.errors.NotFound("image not pulled")
        volumes: dict[str, dict[str, str]] = {}
        for mount in mounts:
            volume_name, mount_path, mode = mount.split(":")
            if not volume_name.startswith("/") and volume_name not in self.volume_map:
                raise docker.errors.NotFound("Volume not created")
            volumes[volume_name] = {
                "mount_path": mount_path,
                "mode": mode,
            }

        envs: dict[str, str] = {}
        for var in env:
            key, value = var.split("=")
            envs[key] = value

        self.service_map[name] = FakeDockerClient.FakeService(
            parent=self, name=name, volumes=volumes, env=envs, endpoint=endpoint_spec
        )

    def login(self, username: str, password: str, registry: str, **kwargs):
        if username != "fredkiss3" or password != "s3cret":
            raise docker.errors.APIError("Bad Credentials")
        self.credentials = dict(username=username, password=password)
        self.is_logged_in = True

    @staticmethod
    def images_search(term: str, limit: int) -> List[DockerImageResultFromRegistry]:
        return [
            {
                "name": "caddy",
                "is_official": True,
                "is_automated": True,
                "description": "Caddy 2 is a powerful, enterprise-ready,"
                " open source web server with automatic HTTPS written in Go",
            },
            {
                "description": "caddy webserver optimized for usage within the SIWECOS project",
                "is_automated": False,
                "is_official": False,
                "name": "siwecos/caddy",
                "star_count": 0,
            },
        ]

    def images_pull(self, repository: str, tag: str = None, *args, **kwargs):
        if tag is not None:
            self.pulled_images.add(f"{repository}:{tag}")
        else:
            self.pulled_images.add(repository)

    def image_get_registry_data(self, image: str, auth_config: dict):
        if auth_config is not None:
            username, password = auth_config["username"], auth_config["password"]
            if username != "fredkiss3" or password != "s3cret":
                raise docker.errors.APIError("Invalid credentials")

            if image == self.NONEXISTANT_PRIVATE_IMAGE:
                raise docker.errors.NotFound(
                    "This image does not exist in the registry"
                )
            self.is_logged_in = True
        else:
            if image == self.NONEXISTANT_IMAGE:
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
