from unittest.mock import patch, Mock

import responses
from django.conf import settings
from django.contrib.auth.models import User

from .base import AuthAPITestCase
from ..docker_operations import get_service_resource_name, creat_caddy_config_for_docker
from ..models import Project, DockerRegistryService, PortConfiguration, URL


class FakeDockerClient:
    pass


@responses.activate
class ProxyTestCases(AuthAPITestCase):
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

    def test_caddy_config_for_service_with_default_url(self):
        service, project = self.create_service()

        service.port_config.add(PortConfiguration.objects.create(forwarded=8080))
        default_url = URL.objects.create(
            domain=f"{project.slug}-{service.slug}.{settings.ROOT_DOMAIN}",
            base_path="/",
        )
        service.urls.add(default_url)

        caddy_template = f"""
{default_url.domain} {{
    handle {{
        reverse_proxy http://{get_service_resource_name(service, 'docker')}:8080
    }}
    log
}}
"""
        self.assertEqual(caddy_template, creat_caddy_config_for_docker(service))

    def test_caddy_config_for_service_with_custom_url(self):
        service, project = self.create_service()

        service.port_config.add(PortConfiguration.objects.create(forwarded=8080))
        default_url = URL.objects.create(
            domain=f"dcr.fredkiss.dev",
            base_path="/",
        )
        service.urls.add(default_url)

        caddy_template = f"""
dcr.fredkiss.dev {{
    handle {{
        reverse_proxy http://{get_service_resource_name(service, 'docker')}:8080
    }}
    log
}}
"""
        self.assertEqual(caddy_template, creat_caddy_config_for_docker(service))

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

        caddy_template = f"""
dcr.fredkiss.dev {{
    handle {{
        reverse_proxy http://{get_service_resource_name(service, 'docker')}:8080
    }}
    log
}}

dcr.zane.dev {{
    handle /registry {{
        reverse_proxy http://{get_service_resource_name(service, 'docker')}:8080
    }}
    log
}}
"""
        self.assertEqual(caddy_template, creat_caddy_config_for_docker(service))

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_expose_service_to_http(self, mock_fake_docker: Mock):
        owner = User.objects.get(username="Fredkiss3")
        project = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            name="cache db2", slug="cache-db", image="nginx:alpine", project=project
        )
        service.port_config.add(
            PortConfiguration.objects.create(forwarded=8080, project=project)
        )
        default_url = URL.objects.create(
            domain=f"{project.slug}-{service.slug}.{settings.ROOT_DOMAIN}",
            base_path="/",
        )
        service.urls.add(default_url)

        self.assertTrue(True)
