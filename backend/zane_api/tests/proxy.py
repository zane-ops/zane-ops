import json
import re
from dataclasses import dataclass
from unittest.mock import patch, Mock, MagicMock

import docker.errors
import responses
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from requests import Request
from rest_framework import status

from .base import AuthAPITestCase
from .service import FakeDockerClientWithServices
from ..docker_operations import get_caddy_id_for_url
from ..models import (
    Project,
    DockerRegistryService,
    URL,
)


class ProxyFakeDockerClient(FakeDockerClientWithServices):
    @dataclass
    class FakeNetwork:
        name: str
        id: str
        parent: "ProxyFakeDockerClient"

        def remove(self):
            self.parent.remove_network(self.name)

    class FakeService:
        def __init__(self):
            self.attrs = {
                "Spec": {
                    "TaskTemplate": {
                        "Networks": [],
                    },
                }
            }

        def update(self, networks: list):
            self.attrs["Spec"]["TaskTemplate"]["Networks"] = [
                {"Target": network} for network in networks
            ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.networks = MagicMock()
        self.services = MagicMock()

        self.network_map = {}  # type: dict[str, ProxyFakeDockerClient.FakeNetwork]
        self.networks.create = self.docker_create_network
        self.networks.get = self.docker_get_network

        self.proxy_service = ProxyFakeDockerClient.FakeService()
        self.services.get.return_value = self.proxy_service

    def docker_create_network(self, name: str, **kwargs):
        created_network = ProxyFakeDockerClient.FakeNetwork(
            name=name, id=name, parent=self
        )
        self.network_map[name] = created_network
        return created_network

    def docker_get_network(self, name: str):
        network = self.network_map.get(name)

        if network is None:
            raise docker.errors.NotFound("network not found")
        return network

    def remove_network(self, name: str):
        network = self.network_map.pop(name)
        if network is None:
            raise docker.errors.NotFound("network not found")


class ProxyResponseStub:
    ADD_ROUTE_URL = (
        f"{settings.CADDY_PROXY_ADMIN_HOST}/config/apps/http/servers/zane/routes"
    )

    def __init__(self):
        self.ids = {}  # type: dict[str, dict]
        self.loggers = set()  # type: set[str]

    @staticmethod
    def get_next_path_segment(url: str) -> str:
        match = re.search(r"/id/([^/]+)", url)
        return match.group(1) if match else None

    def response_callback(self, request: Request):
        if request.method.upper() == "GET":
            if "/id/zane-server/logs/logger_names/" in request.url:
                splitted = request.url.split("/")
                if len(splitted[-1]) == 0:
                    logger = splitted[-2]
                else:
                    logger = splitted[-1]
                if logger in self.loggers:
                    return 200, {}, json.dumps("")
                else:
                    return 200, {}, json.dumps(None)
            _id = self.get_next_path_segment(request.url)
            if _id is not None:
                item = self.ids.get(_id)
                if item:
                    return 200, {}, json.dumps(item)
                else:
                    return 404, {}, json.dumps("")

        if request.method.upper() == "POST" or request.method.upper() == "PATCH":
            payload = json.loads(request.body)
            print(request.url, payload)

            if "/id/zane-server/logs/logger_names/" in request.url:
                splitted = request.url.split("/")
                if len(splitted[-1]) == 0:
                    logger = splitted[-2]
                else:
                    logger = splitted[-1]
                self.loggers.add(logger)
                return 200, {}, json.dumps("")

            if request.url == ProxyResponseStub.ADD_ROUTE_URL:
                domain_id = payload.get("@id")
                self.ids[domain_id] = payload

                routes = payload["handle"][0]["routes"]
                for route in routes:
                    self.ids[route.get("@id")] = route

                return 200, {}, json.dumps("")

            if "/handle/0/routes" in request.url:
                route_id = payload.get("@id")
                self.ids[route_id] = payload
                return 200, {}, json.dumps("")

            _id = self.get_next_path_segment(request.url)
            if _id is not None:
                self.ids[_id] = payload

                if (
                    payload.get("match") is not None
                    and payload.get("match")[0].get("host") is not None
                ):
                    routes = payload["handle"][0]["routes"]
                    for route in routes:
                        self.ids[route.get("@id")] = route
                return 200, {}, json.dumps("")
            return 200, {}, json.dumps("")


class ZaneProxyTestCases(AuthAPITestCase):
    @staticmethod
    def create_service():
        owner = User.objects.get(username="Fredkiss3")
        project = Project.objects.create(slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            name="sample webserver",
            slug="sample-webserver",
            image="nginx:alpine",
            project=project,
        )
        return service, project

    @staticmethod
    def register_responses():
        response_stub = ProxyResponseStub()
        responses.add_callback(
            responses.POST,
            re.compile(f"{settings.CADDY_PROXY_ADMIN_HOST}/\\w+"),
            callback=response_stub.response_callback,
            content_type="application/json",
        )
        responses.add_callback(
            responses.PATCH,
            re.compile(f"{settings.CADDY_PROXY_ADMIN_HOST}/\\w+"),
            callback=response_stub.response_callback,
            content_type="application/json",
        )
        responses.add_callback(
            responses.GET,
            re.compile(f"{settings.CADDY_PROXY_ADMIN_HOST}/\\w+"),
            callback=response_stub.response_callback,
            content_type="application/json",
        )
        return response_stub

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_successfull(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        default_service_url = URL(
            domain=f"sandbox-basic-http-webserver.{settings.ROOT_DOMAIN}",
            base_path="/",
        )
        stub = self.register_responses()
        create_service_payload = {
            "name": "Basic HTTP webserver",
            "image": "nginx:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertTrue(default_service_url.domain in stub.ids)
        self.assertTrue(get_caddy_id_for_url(default_service_url) in stub.ids)

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_to_http_default_base_path(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        default_service_url = URL(
            domain=f"site.com",
            base_path="/",
        )
        stub = self.register_responses()
        create_service_payload = {
            "name": "Basic HTTP webserver",
            "image": "nginx:latest",
            "urls": [
                {
                    "domain": default_service_url.domain,
                    "base_path": default_service_url.base_path,
                }
            ],
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        print(stub.ids[get_caddy_id_for_url(default_service_url)])
        self.assertEqual(
            "/*",
            stub.ids[get_caddy_id_for_url(default_service_url)].get("match")[0]["path"][
                0
            ],
        )

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_to_http_with_custom_path(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        default_service_url = URL(
            domain=f"thullo.zane.local",
            base_path="/api",
        )
        stub = self.register_responses()
        create_service_payload = {
            "name": "Basic HTTP webserver",
            "image": "nginx:latest",
            "urls": [
                {
                    "domain": default_service_url.domain,
                    "base_path": default_service_url.base_path,
                }
            ],
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(
            stub.ids[get_caddy_id_for_url(default_service_url)].get("match")
        )
        matched_path = stub.ids[get_caddy_id_for_url(default_service_url)].get("match")[
            0
        ]["path"][0]
        self.assertEqual("/api/*", matched_path)

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_to_http_path_order_by_path_length(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        stub = self.register_responses()
        create_service1_payload = {
            "name": "thullo front",
            "image": "dcr.fredkiss.dev/thullo-front:latest",
            "urls": [
                {
                    "domain": f"thullo.zane.local",
                }
            ],
        }

        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service1_payload),
            content_type="application/json",
        )

        create_service2_payload = {
            "name": "thullo api",
            "image": "dcr.fredkiss.dev/thullo-api:latest",
            "urls": [
                {
                    "domain": f"thullo.zane.local",
                    "base_path": "/api",
                }
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service2_payload),
            content_type="application/json",
        )

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(stub.ids.get("thullo.zane.local"))
        expected_path_order = ["/api/*", "/*"]
        stub_routes = stub.ids.get("thullo.zane.local")["handle"][0]["routes"]
        actual_paths = [route["match"][0]["path"][0] for route in stub_routes]
        self.assertIsNotNone(stub.ids.get("thullo.zane.local"))
        self.assertEqual(expected_path_order, actual_paths)

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_to_http_includes_strip_prefix_if_true(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        stub = self.register_responses()
        custom_url = URL(
            domain="thullo.zane.local",
            base_path="/api",
            strip_prefix=True,
        )
        create_service_payload = {
            "name": "thullo api",
            "image": "dcr.fredkiss.dev/thullo-api:latest",
            "urls": [
                {
                    "domain": custom_url.domain,
                    "base_path": custom_url.base_path,
                    "strip_prefix": custom_url.strip_prefix,
                }
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(stub.ids.get(get_caddy_id_for_url(custom_url)))
        url_config = stub.ids.get(get_caddy_id_for_url(custom_url))

        url_config_handle = url_config["handle"][0]["routes"][0]["handle"]
        self.assertEqual(2, len(url_config_handle))
        self.assertEqual(
            {"handler": "rewrite", "strip_path_prefix": "/api"}, url_config_handle[0]
        )

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_to_http_does_not_includes_strip_prefix_if_false(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        stub = self.register_responses()
        custom_url = URL(
            domain="thullo.zane.local",
            base_path="/api",
            strip_prefix=False,
        )
        create_service_payload = {
            "name": "thullo api",
            "image": "dcr.fredkiss.dev/thullo-api:latest",
            "urls": [
                {
                    "domain": custom_url.domain,
                    "base_path": custom_url.base_path,
                    "strip_prefix": custom_url.strip_prefix,
                }
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(stub.ids.get(get_caddy_id_for_url(custom_url)))
        url_config = stub.ids.get(get_caddy_id_for_url(custom_url))

        url_config_handle = url_config["handle"][0]["routes"][0]["handle"]
        self.assertEqual(1, len(url_config_handle))
        self.assertIsNone(url_config_handle[0].get("strip_path_prefix"))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_attach_network_to_proxy_when_creating_project(
        self, mock_fake_docker_client: Mock
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={
                "slug": "zane-ops",
            },
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        fake_docker_client: ProxyFakeDockerClient = mock_fake_docker_client.return_value
        self.assertEqual(
            1,
            len(
                fake_docker_client.proxy_service.attrs["Spec"]["TaskTemplate"][
                    "Networks"
                ]
            ),
        )

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_detach_network_to_proxy_when_archiving_project(
        self, mock_fake_docker_client: Mock
    ):
        self.loginUser()
        self.client.post(
            reverse("zane_api:projects.list"),
            data={
                "slug": "zane-ops",
            },
        )
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        fake_docker_client: ProxyFakeDockerClient = mock_fake_docker_client.return_value
        self.assertEqual(
            0,
            len(
                fake_docker_client.proxy_service.attrs["Spec"]["TaskTemplate"][
                    "Networks"
                ]
            ),
        )
