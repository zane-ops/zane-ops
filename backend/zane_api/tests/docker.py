from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase, FakeDockerClient


class DockerViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.loginUser()

    def test_search_docker_images(self):
        response = self.client.get(
            reverse("zane_api:docker.image_search"), QUERY_STRING="q=caddy"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertIsNotNone(response.json().get("images"))
        images = response.json().get("images")
        self.assertEqual(images[0]["full_image"], "caddy")
        self.assertEqual(images[1]["full_image"], "siwecos/caddy")

    def test_search_query_empty(self):
        response = self.client.get(reverse("zane_api:docker.image_search"))
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class DockerPortMappingViewTests(AuthAPITestCase):
    def test_successfull(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 8082,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), True)

    def test_unavailable_port(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": FakeDockerClient.PORT_USED_BY_HOST,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), False)
