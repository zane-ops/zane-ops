from unittest.mock import patch

from .base import APITestCase


class FakeDockerClient:
    pass


class ProxyTestCases(APITestCase):
    @patch("zane_api.docker_utils.get_docker_client", return_value=FakeDockerClient())
    def test_expose_service_to_http(self):
        pass
