from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status


class ProxyViewTestCase(AuthAPITestCase):
    def test_check_certificate_succesfull(self):
        _, service = self.create_and_deploy_caddy_docker_service()

        url = service.urls.first()
        response = self.client.get(
            reverse("zane_api:proxy.check_certificates"),
            QUERY_STRING=f"domain={url.domain}",  # type: ignore
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_check_certificate_unsuccesfull(self):
        response = self.client.get(
            reverse("zane_api:proxy.check_certificates"),
            QUERY_STRING=f"domain=hello.fkiss.me",  # type: ignore
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
