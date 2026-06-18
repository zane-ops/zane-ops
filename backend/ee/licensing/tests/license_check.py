from typing import cast

from django.urls import reverse
from rest_framework import status

from ..models import License, LicenseData, LicenceFeature, InstanceMeta, LicenseTiers
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import mock_remote_api_for_licensing, LicenseMockScenario
import responses


# Recurring schedule that periodically re-checks the installed license against
# the remote API (see `POST /v1/license/check`). The instance holds a single
# license (singleton), so the schedule id is a constant.
LICENSE_CHECK_SCHEDULE_ID = "license-check"


class LicenceCheckViewTests(AuthAPITestCase):
    @responses.activate
    async def test_license_install_should_create_a_schedule_for_license_check(self):
        await self.aLoginUser()

        with mock_remote_api_for_licensing():
            response = await self.async_client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            self.assertIsNotNone(await License.aget())

            # installing a license registers the recurring license-check schedule
            schedule_handle = self.get_workflow_schedule_by_id(
                LICENSE_CHECK_SCHEDULE_ID
            )
            self.assertIsNotNone(schedule_handle)
            self.assertEqual(1, len(self.workflow_schedules))

    @responses.activate
    async def test_license_uninstall_should_delete_the_schedule_for_license_check(self):
        await self.aLoginUser()

        with mock_remote_api_for_licensing():
            # install a license -> schedule is created
            response = await self.async_client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            if self.commit_callback is not None:
                await self.commit_callback()

            self.assertIsNotNone(
                self.get_workflow_schedule_by_id(LICENSE_CHECK_SCHEDULE_ID)
            )

            # uninstall the license -> schedule is removed
            response = await self.async_client.delete(
                reverse("licensing:license.uninstall"),
            )
            self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

            self.assertIsNone(await License.aget())
            self.assertIsNone(
                self.get_workflow_schedule_by_id(LICENSE_CHECK_SCHEDULE_ID)
            )
            self.assertEqual(0, len(self.workflow_schedules))

    @responses.activate
    async def test_license_schedule_workflow(self):
        pass
