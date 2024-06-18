from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase
from ..docker_operations import (
    create_docker_volume,
)
from ..models import Project, Volume, DockerRegistryService


class DockerVolumeTests(AuthAPITestCase):
    def test_create_volume_successful(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zane-ops", owner=owner)
        service = DockerRegistryService.objects.create(project=p)
        volume = Volume.objects.create(
            name="postgres DB Data",
        )
        create_docker_volume(volume, service)
        self.assertEqual(1, len(self.fake_docker_client.volume_map))


class VolumeGetSizeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)

    def test_get_volume_size(self):
        volume = Volume.objects.create(
            name="postgres DB Data",
        )

        response = self.client.get(
            reverse("zane_api:volume.size", kwargs={"volume_id": volume.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertIsNotNone(data.get("size"))

    def test_non_existant_volume(self):
        response = self.client.get(
            reverse("zane_api:volume.size", kwargs={"volume_id": "abcDefGh1jk"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
