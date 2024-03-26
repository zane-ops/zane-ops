import json
from dataclasses import dataclass
from unittest.mock import patch, Mock, MagicMock

import docker.errors
import responses
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from .service import FakeDockerClientWithServices
from ..docker_operations import expose_docker_service_to_http
from ..models import (
    Project,
    DockerRegistryService,
    PortConfiguration,
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


class ZaneProxyTestCases(AuthAPITestCase):
    def create_service(self):
        owner = User.objects.get(username="Fredkiss3")
        project = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            name="sample webserver",
            slug="sample-webserver",
            image="nginx:alpine",
            project=project,
        )
        return service, project

    @staticmethod
    def register_default_responses_for_url(url: URL):
        # Domain config
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}",
            status=status.HTTP_404_NOT_FOUND,
        )

        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/config/apps/http/servers/zane/routes",
            status=status.HTTP_200_OK,
        )

        # logs
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/{url.domain}",
            body=json.dumps(None),
            headers={"content-type": "application/json"},
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/{url.domain}",
            status=status.HTTP_200_OK,
        )

        # Base path config
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}-",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{url.domain}/handle/0/routes",
            status=status.HTTP_404_NOT_FOUND,
        )

    @responses.activate
    def test_expose_service_to_http_with_default_url(self):
        service, project = self.create_service()

        service.port_config.add(PortConfiguration.objects.create(forwarded=8080))
        default_url = URL.objects.create(
            domain=f"{project.slug}-{service.slug}.{settings.ROOT_DOMAIN}",
            base_path="/",
        )
        service.urls.add(default_url)

        # Domain config
        self.register_default_responses_for_url(default_url)

        expose_docker_service_to_http(service)
        self.assertEqual(6, len(responses.calls))

    @responses.activate
    def test_caddy_config_for_service_with_custom_url(self):
        service, project = self.create_service()

        service.port_config.add(PortConfiguration.objects.create(forwarded=8080))
        custom_url = URL.objects.create(
            domain=f"dcr.fredkiss.dev",
            base_path="/",
        )
        service.urls.add(custom_url)

        self.register_default_responses_for_url(custom_url)

        expose_docker_service_to_http(service)
        self.assertEqual(6, len(responses.calls))

    @responses.activate
    def test_caddy_config_for_service_with_multiple_domains(self):
        service, project = self.create_service()

        service.port_config.add(PortConfiguration.objects.create(forwarded=8080))
        urls = URL.objects.bulk_create(
            [
                URL(
                    domain=f"dcr.fredkiss.dev",
                    base_path="/",
                ),
                URL(
                    domain=f"dcr.zane.dev",
                    base_path="/registry",
                ),
            ]
        )
        service.urls.add(*urls)

        # 1st URL
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/config/apps/http/servers/zane/routes",
            status=status.HTTP_200_OK,
        )

        # logs
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.fredkiss.dev",
            body=json.dumps(None),
            headers={"content-type": "application/json"},
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.fredkiss.dev",
            status=status.HTTP_200_OK,
        )

        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev-",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev/handle/0/routes",
            status=status.HTTP_404_NOT_FOUND,
        )

        # 2nd URL
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.zane.dev",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/config/apps/http/servers/zane/routes",
            status=status.HTTP_200_OK,
        )

        # logs
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.zane.dev",
            body=json.dumps(None),
            headers={"content-type": "application/json"},
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.zane.dev",
            status=status.HTTP_200_OK,
        )

        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.zane.dev-registry",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.zane.dev/handle/0/routes",
            status=status.HTTP_404_NOT_FOUND,
        )

        expose_docker_service_to_http(service)
        self.assertEqual(12, len(responses.calls))

    @responses.activate
    def test_caddy_config_for_service_with_multiple_urls_but_not_same_domain(self):
        service, project = self.create_service()

        service.port_config.add(PortConfiguration.objects.create(forwarded=8080))
        urls = URL.objects.bulk_create(
            [
                URL(
                    domain=f"dcr.fredkiss.dev",
                    base_path="/",
                ),
                URL(
                    domain=f"dcr.fredkiss.dev",
                    base_path="/registry",
                ),
            ]
        )
        service.urls.add(*urls)

        # 1st URL
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/config/apps/http/servers/zane/routes",
            status=status.HTTP_200_OK,
        )

        # logs
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.fredkiss.dev",
            body=json.dumps(None),
            headers={"content-type": "application/json"},
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.fredkiss.dev",
            status=status.HTTP_200_OK,
        )
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/zane-server/logs/logger_names/dcr.fredkiss.dev",
            body=json.dumps(""),
            headers={"content-type": "application/json"},
        )

        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev-",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev/handle/0/routes",
            status=status.HTTP_404_NOT_FOUND,
        )
        # 2nd URL
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev",
            status=status.HTTP_200_OK,
        )
        responses.add(
            responses.GET,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev-registry",
            status=status.HTTP_404_NOT_FOUND,
        )
        responses.add(
            responses.POST,
            url=f"{settings.CADDY_PROXY_ADMIN_HOST}/id/dcr.fredkiss.dev/handle/0/routes",
            status=status.HTTP_404_NOT_FOUND,
        )

        expose_docker_service_to_http(service)
        self.assertEqual(10, len(responses.calls))

    @responses.activate
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=ProxyFakeDockerClient(),
    )
    def test_api_expose_service_to_http(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(name="Sandbox", slug="sandbox", owner=owner)

        self.register_default_responses_for_url(
            URL(
                domain=f"sandbox-basic-http-webserver.{settings.ROOT_DOMAIN}",
                base_path="/",
            )
        )
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

        self.assertEqual(6, len(responses.calls))

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
                "name": "Zane Ops",
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
                "name": "Zane Ops",
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
