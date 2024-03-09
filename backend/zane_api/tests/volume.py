from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock


class FakeDockerClient:
    def __init__(self):
        self.volumes = MagicMock()


@patch("zane_api.views.docker.DockerService._get_client", wraps=FakeDockerClient)
class DockerVolumeTests(TestCase):
    def test_create_volume(self, mock_fake_docker: Mock):
        pass
