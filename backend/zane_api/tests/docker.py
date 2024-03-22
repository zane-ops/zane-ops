from typing import List
from unittest.mock import patch, Mock, MagicMock

import docker.errors
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..docker_utils import DockerImageResultFromRegistry


class FakeDockerClient:
    def __init__(self):
        self.containers = MagicMock()
        self.images = MagicMock()

        self.containers.run = self.containers_run
        self.images.search = self.images_search

    @staticmethod
    def containers_run(image: str, ports: dict[str, tuple[str, int]], command: str, remove: bool):
        _, port = list(ports.values())[0]
        if port == 90:
            raise docker.errors.APIError("Port 90 is already used")

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

    @staticmethod
    def login(username: str, password: str, **kwargs):
        if username != 'user' or password != 'password':
            raise docker.errors.APIError("Bad Credentials")


class DockerViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.loginUser()

    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_search_docker_images(self, mock_fake_docker: Mock):
        response = self.client.get(
            reverse("zane_api:docker.image_search"), QUERY_STRING="q=caddy"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertIsNotNone(response.json().get("images"))
        images = response.json().get("images")
        self.assertEqual(images[0]["full_image"], "library/caddy:latest")
        self.assertEqual(images[1]["full_image"], "siwecos/caddy:latest")

    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_search_query_empty(self, _: Mock):
        response = self.client.get(reverse("zane_api:docker.image_search"))
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_success_validate_credentials(self, _: Mock):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "username": "user",
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_bad_credentials(self, _: Mock):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "username": "bad",
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_bad_request_for_credentials(self, _: Mock):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)


class DockerPortMappingViewTests(AuthAPITestCase):
    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_successfull(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 8080,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), True)

    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_unavailable_port(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 90,
            },
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(response.json().get("available"), False)
