from unittest.mock import patch, Mock

from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase
from ..models import Project


class FakeDockerClient:
    pass


class DockerServiceCreateViewTest(AuthAPITestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClient())
    def test_create_service_succesfull(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(name="KISS CAM", slug="kiss-cam", owner=owner)

        create_redis_payload = {
            "name": "cache_db",
            "is_public": False,
            "spec": {
                "command": "redis-server --requirepass ${REDIS_PASSWORD}",
                "env": {
                    "REDIS_PASSWORD": "strongPassword123"
                },
                "image": "redis:alpine",
                "volumes": [
                    {
                        "name": "redis_data_volume",
                        "size": {
                            "n": 1,
                            "unit": "GB"
                        },
                        "mount_path": "/data"
                    }
                ]
            }
        }

        response = self.client.post(
            reverse('zane_api:services.docker', kwargs={"project_slug": p.slug}),
            data=create_redis_payload
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
