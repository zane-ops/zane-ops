from typing import cast
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import URL
from compose.tests.stacks import ComposeStackAPITestBase
from compose.tests.fixtures import DOCKER_COMPOSE_WEB_SERVICE


class ProxyViewTestCase(AuthAPITestCase):
    def test_check_certificate_succesfull(self):
        _, service = self.create_and_deploy_caddy_docker_service()

        url = cast(URL, service.urls.first())
        response = self.client.get(
            reverse("zane_api:proxy.check_certificates"),
            QUERY_STRING=f"domain={url.domain}",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_check_certificate_unsuccesfull(self):
        response = self.client.get(
            reverse("zane_api:proxy.check_certificates"),
            QUERY_STRING="domain=hello.fkiss.me",
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class ComposeProxyViewTestCase(ComposeStackAPITestBase):
    def test_check_certificate_for_compose_stack(self):
        _, stack = self.create_compose_stack(content=DOCKER_COMPOSE_WEB_SERVICE)

        # Set URLs directly (deploy requires Temporal which isn't available in unit tests)
        stack.urls = {
            "web": [
                {
                    "domain": "hello.127-0-0-1.sslip.io",
                    "base_path": "/",
                    "strip_prefix": True,
                    "port": 80,
                }
            ]
        }
        stack.save()

        response = self.client.get(
            reverse("zane_api:proxy.check_certificates"),
            QUERY_STRING="domain=hello.127-0-0-1.sslip.io",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
