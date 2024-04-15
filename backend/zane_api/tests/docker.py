from unittest.mock import patch, Mock

from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase, FakeDockerClient


class DockerViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.loginUser()

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_search_docker_images(self, mock_fake_docker: Mock):
        response = self.client.get(
            reverse("zane_api:docker.image_search"), QUERY_STRING="q=caddy"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertIsNotNone(response.json().get("images"))
        images = response.json().get("images")
        self.assertEqual(images[0]["full_image"], "library/caddy:latest")
        self.assertEqual(images[1]["full_image"], "siwecos/caddy:latest")

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_search_query_empty(self, _: Mock):
        response = self.client.get(reverse("zane_api:docker.image_search"))
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_success_validate_credentials(self, _: Mock):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "username": "fredkiss3",
                "password": "s3cret",
            },
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_bad_credentials(self, _: Mock):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "username": "bad",
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_bad_request_for_credentials(self, _: Mock):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class DockerPortMappingViewTests(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_successfull(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 8082,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), True)

    @patch(
        "zane_api.docker_operations.get_docker_client", return_value=FakeDockerClient()
    )
    def test_unavailable_port(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": FakeDockerClient.PORT_USED_BY_HOST,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), False)
