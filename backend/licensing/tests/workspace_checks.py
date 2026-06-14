from typing import cast

from django.urls import reverse
from rest_framework import status

from ..models import License, LicenseData, LicenceFeature, InstanceMeta, LicenseTiers
from zane_api.models import Workspace
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import mock_remote_api_for_licensing, LicenseMockScenario
import responses


class WorkspaceLimitsChecksViewTests(AuthAPITestCase):
    @responses.activate
    def test_cannot_create_more_than_one_workspace_without_installed_license(self):
        self.loginUser()
        self.assertIsNotNone(Workspace.objects.first())

        response = self.client.post(
            reverse("zane_api:workspaces.create"),
            data={"name": "Fredkiss's work"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_cannot_create_more_than_one_workspace_without_valid_license(self):
        self.loginUser()
        self.assertIsNotNone(Workspace.objects.first())

        with mock_remote_api_for_licensing(tier=LicenseTiers.FREE):
            # Install free license
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )

            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)
            self.assertEqual(LicenseTiers.FREE, installed_license.tier)

            # create workspace
            response = self.client.post(
                reverse("zane_api:workspaces.create"),
                data={"name": "Fredkiss's work"},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_should_be_able_to_create_more_than_one_workspace_with_valid_license(self):
        self.loginUser()
        self.assertIsNotNone(Workspace.objects.first())

        with mock_remote_api_for_licensing():
            # Install License
            license_uuid = str(uuid4())
            data = {"uuid": license_uuid}
            response = self.client.post(
                reverse("licensing:license.install"),
                data=data,
            )

            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)

            # Create workspace
            response = self.client.post(
                reverse("zane_api:workspaces.create"),
                data={"name": "Fredkiss's work"},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
