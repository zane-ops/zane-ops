from django.conf import settings
from django.urls import reverse
from rest_framework import status

from ..models import License
from ..schedules import CheckLicenseWorkflow
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import (
    amock_remote_api_for_licensing,
    LicenseMockScenario,
)
import responses
from ..constants import LICENSE_CHECK_SCHEDULE_ID


class LicenceCheckViewTests(AuthAPITestCase):
    @responses.activate
    async def test_license_install_should_create_a_schedule_for_license_check(self):
        await self.aLoginUser()

        async with amock_remote_api_for_licensing():
            response = await self.async_client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            self.assertIsNotNone(await License.aget())

            schedule_handle = self.get_workflow_schedule_by_id(
                LICENSE_CHECK_SCHEDULE_ID
            )
            self.assertIsNotNone(schedule_handle)
            self.assertEqual(1, len(self.workflow_schedules))

    @responses.activate
    async def test_license_uninstall_should_delete_the_schedule_for_license_check(self):
        await self.aLoginUser()

        async with amock_remote_api_for_licensing():
            # install a license -> schedule is created on commit

            response = await self.async_client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            self.assertIsNotNone(
                self.get_workflow_schedule_by_id(LICENSE_CHECK_SCHEDULE_ID)
            )
            self.assertEqual(1, len(self.workflow_schedules))

            # uninstall the license -> schedule is removed on commit
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
    async def test_license_schedule_workflow_keeps_valid_license(self):
        async with self.workflowEnvironment() as env:
            await self.aLoginUser()

            license_uuid = str(uuid4())
            # install + check must run under the same mock so the ephemeral
            # signing key stays consistent across both calls.
            async with amock_remote_api_for_licensing():
                response = await self.async_client.post(
                    reverse("licensing:license.install"),
                    data={"uuid": license_uuid},
                )
                self.assertEqual(status.HTTP_201_CREATED, response.status_code)

                result = await env.client.execute_workflow(
                    CheckLicenseWorkflow.run,
                    license_uuid,
                    id=f"{LICENSE_CHECK_SCHEDULE_ID}-valid",
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                self.assertEqual("valid", result)
                self.assertIsNotNone(await License.aget())

    @responses.activate
    async def test_license_schedule_workflow_removes_license_on_fingerprint_mismatch(
        self,
    ):
        async with self.workflowEnvironment() as env:
            await self.aLoginUser()

            license_uuid = str(uuid4())
            async with amock_remote_api_for_licensing(
                scenario=LicenseMockScenario.CHECK_FINGERPRINT_MISMATCH
            ):
                # install still succeeds (the mismatch only affects `check`)
                response = await self.async_client.post(
                    reverse("licensing:license.install"),
                    data={"uuid": license_uuid},
                )
                self.assertEqual(status.HTTP_201_CREATED, response.status_code)
                self.assertIsNotNone(await License.aget())

                result = await env.client.execute_workflow(
                    CheckLicenseWorkflow.run,
                    license_uuid,
                    id=f"{LICENSE_CHECK_SCHEDULE_ID}-mismatch",
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                self.assertEqual("removed", result)
                self.assertIsNone(await License.aget())
