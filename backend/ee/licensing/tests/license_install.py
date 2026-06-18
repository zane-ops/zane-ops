from typing import cast

from django.urls import reverse
from rest_framework import status

from ..models import License, LicenseData, LicenceFeature, InstanceMeta, LicenseTiers
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import mock_remote_api_for_licensing, LicenseMockScenario
import responses


class LicenceInstallViewTests(AuthAPITestCase):
    @responses.activate
    def test_install_license_successfully(self):
        user = self.loginUser()

        license_uuid = str(uuid4())
        data = {"uuid": license_uuid}
        with mock_remote_api_for_licensing():
            response = self.client.post(
                reverse("licensing:license.install"),
                data=data,
            )

            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)

            self.assertEqual(installed_license.installed_by, user)

            data = cast(LicenseData, installed_license._data)
            self.assertIsNotNone(data)
            self.assertEqual(license_uuid, data.uuid)
            self.assertEqual(data.fingerprint, InstanceMeta.get_fingerprint())
            self.assertTrue(
                installed_license.is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES)
            )
            self.assertTrue(
                installed_license.is_feature_enabled(LicenceFeature.EXTRA_USER_SEATS)
            )

    @responses.activate
    def test_install_free_tier_license_disables_paid_features(self):
        self.loginUser()

        with mock_remote_api_for_licensing(tier=LicenseTiers.FREE):
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
                installed_license.is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES)
            )
            self.assertFalse(
                installed_license.is_feature_enabled(LicenceFeature.EXTRA_USER_SEATS)
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
                responses.reset()  # used to prevent `responses.activate` to raise an error on repeated calls
                with mock_remote_api_for_licensing(scenario=scenario):
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
        # no `loginUser()` -> anonymous request
        with mock_remote_api_for_licensing():
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

    @responses.activate
    def test_install_license_overwrites_existing_license(self):
        self.loginUser()

        # install a first license
        with mock_remote_api_for_licensing(tier=LicenseTiers.STARTER):
            first_uuid = str(uuid4())
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": first_uuid},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # installing a second license overwrites the first (singleton)
        responses.reset()
        with mock_remote_api_for_licensing(tier=LicenseTiers.STARTER):
            second_uuid = str(uuid4())
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": second_uuid},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            self.assertEqual(1, License.objects.count())

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)
            data = cast(LicenseData, installed_license._data)
            self.assertEqual(second_uuid, data.uuid)
            self.assertEqual(LicenseTiers.STARTER, installed_license.tier)


class LicenceUnInstallViewTests(AuthAPITestCase):
    @responses.activate
    def test_uninstall_license_successfully(self):
        self.loginUser()

        license_uuid = str(uuid4())
        data = {"uuid": license_uuid}
        with mock_remote_api_for_licensing():
            # install license
            response = self.client.post(
                reverse("licensing:license.install"),
                data=data,
            )

            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)

            # uninstall license
            response = self.client.delete(
                reverse("licensing:license.uninstall"),
            )

            self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

            self.assertIsNone(License.get())

            # uninstall must call the remote unbind endpoint
            unbind_calls = [
                call
                for call in responses.calls
                if cast(str, call.request.url).endswith("/v1/license/unbind")
            ]
            self.assertEqual(1, len(unbind_calls))

    @responses.activate
    def test_uninstall_license_not_being_installed_returns_404(self):
        self.loginUser()
        response = self.client.delete(
            reverse("licensing:license.uninstall"),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @responses.activate
    def test_uninstall_license_keeps_license_when_unbind_fails(self):
        self.loginUser()

        failing_scenarios = [
            LicenseMockScenario.UNBIND_FINGERPRINT_MISMATCH,
            LicenseMockScenario.UNBIND_REBIND_LIMIT,
        ]

        for scenario in failing_scenarios:
            with self.subTest(scenario=scenario):
                responses.reset()  # prevent `responses.activate` from raising on repeated calls

                with mock_remote_api_for_licensing(scenario=scenario):
                    # install license (happy path for the install endpoint)
                    response = self.client.post(
                        reverse("licensing:license.install"),
                        data={"uuid": str(uuid4())},
                    )
                    self.assertEqual(status.HTTP_201_CREATED, response.status_code)
                    self.assertIsNotNone(License.get())

                    # unbind fails -> license must NOT be deleted from the instance
                    response = self.client.delete(
                        reverse("licensing:license.uninstall"),
                    )

                    self.assertEqual(
                        status.HTTP_400_BAD_REQUEST, response.status_code, scenario
                    )
                    jprint(response.json())
                    self.assertIsNotNone(License.get(), scenario)
