from typing import cast

from django.urls import reverse
from rest_framework import status

from ..models import License, LicenseData, LicenceFeature, InstanceMeta, LicenseTiers
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import mock_remote_api_for_licensing, LicenseMockScenario
import responses

"""
License install workflow:
1. Install from a UUID
2. Download the license data from the remote API (using the UUID)
3. Validate license data with public key
4. Save license data in the DB
"""


class LicenceInstallViewTests(AuthAPITestCase):
    @responses.activate
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

    @responses.activate
    def test_install_free_tier_license_disables_paid_features(self):
        mock_remote_api_for_licensing(tier=LicenseTiers.FREE)
        self.loginUser()

        response = self.client.post(
            reverse("licensing:license.install"),
            data={"uuid": str(uuid4())},
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        installed_license = cast(License, License.get())
        self.assertIsNotNone(installed_license)
        self.assertTrue(installed_license.is_valid)
        self.assertEqual(LicenseTiers.FREE, installed_license.tier)
        self.assertFalse(
            installed_license.is_feature_enabled(LicenceFeature.UNLIMITED_WORKSPACES)
        )

    @responses.activate
    def test_install_license_fails_for_invalid_remote_responses(self):
        self.loginUser()

        failing_scenarios = [
            LicenseMockScenario.NOT_FOUND,
            LicenseMockScenario.MALFORMED_RESPONSE,
            LicenseMockScenario.INVALID_SIGNATURE,
            LicenseMockScenario.MALFORMED_TOKEN,
            LicenseMockScenario.EXPIRED,
            LicenseMockScenario.FINGERPRINT_MISMATCH,
            LicenseMockScenario.UUID_MISMATCH,
        ]

        for scenario in failing_scenarios:
            with self.subTest(scenario=scenario):
                responses.reset()
                mock_remote_api_for_licensing(scenario=scenario)

                response = self.client.post(
                    reverse("licensing:license.install"),
                    data={"uuid": str(uuid4())},
                )

                jprint(response.json())

                self.assertEqual(
                    status.HTTP_400_BAD_REQUEST, response.status_code, scenario
                )
                self.assertIsNone(License.get(), scenario)

    @responses.activate
    def test_install_license_requires_instance_owner(self):
        mock_remote_api_for_licensing()
        # no `loginUser()` -> anonymous request

        response = self.client.post(
            reverse("licensing:license.install"),
            data={"uuid": str(uuid4())},
        )

        jprint(response.json())
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIsNone(License.get())
