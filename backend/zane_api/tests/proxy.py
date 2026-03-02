from typing import cast
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import URL


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
