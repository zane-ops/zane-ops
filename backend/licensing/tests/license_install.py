from typing import cast

from django.urls import reverse
from rest_framework import status

from ..models import License, LicenseData, LicenceFeature, InstanceMeta
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import mock_remote_api_for_licensing
import responses

"""
License install workflow:
1. Install from a UUID
2. Download the license data from the remote API (using the UUID)
3. Validate license data with public key
4. Save license data in the DB
"""


class LicenceInstallViewTests(AuthAPITestCase):
    @responses.activate()
    def test_install_license_successfully(self):
        mock_remote_api_for_licensing()
        user = self.loginUser()

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

        self.assertEqual(installed_license.installed_by, user)

        data = cast(LicenseData, installed_license._decode())
        self.assertIsNotNone(data)
        self.assertEqual(license_uuid, data.uuid)
        self.assertEqual(data.fingerprint, InstanceMeta.get_fingerprint())
        self.assertTrue(
            installed_license.is_feature_enabled(LicenceFeature.UNLIMITED_WORKSPACES)
        )
