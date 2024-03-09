from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock


class FakeDockerClient:
    def __init__(self, raise_error: bool = False):
        self.volumes = MagicMock()
        self.raise_error = raise_error

        self.volumes.create = self.volumes_create

    def volumes_create(self, **kwargs):
        pass


class DockerVolumeTests(TestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_volume(self, mock_fake_docker: Mock):
        pass
