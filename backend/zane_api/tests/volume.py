from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase
from ..models import Project, Volume


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
