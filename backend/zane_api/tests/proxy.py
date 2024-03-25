import json
from unittest.mock import patch, Mock

import responses
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from .service import FakeDockerClient
from ..docker_operations import expose_docker_service_to_http
from ..models import (
    Project,
    DockerRegistryService,
    PortConfiguration,
    URL,
    DockerDeployment,
)


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
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_api_expose_service_to_http(
        self,
        _: Mock,
    ):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        self.register_default_responses_for_url(
            URL(domain=f"kiss-cam-adminer-ui.{settings.ROOT_DOMAIN}", base_path="/")
        )
        create_service_payload = {
            "name": "Adminer UI",
            "image": "adminer:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        first_deployment = DockerDeployment.objects.get(service__slug="adminer-ui")
        print(first_deployment.get_task_id())
        deploy_task_result = AsyncResult(first_deployment.get_task_id())
        self.assertEqual("SUCCESS", deploy_task_result.status)
        self.assertEqual(6, len(responses.calls))
