from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import Project


# from ..workflows import GetProjectWorkflow


class SimpleTemporalViewTests(AuthAPITestCase):
    async def test_temporal_view(self):
        owner = await self.aLoginUser()
        await Project.objects.acreate(slug="sandbox", owner=owner)
        async with self.workflowEnvironment() as (env, worker):
            response = await self.async_client.post(
                reverse(
                    "zane_api:temporal.test_workflow",
                ),
                data={"slug": "sandbox"},
            )
            data = response.json()
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertIsNotNone(data.get("workflow_id"))
            # handle = env.client.get_workflow_handle(data.get("workflow_id"))
            # project = await handle.query(GetProjectWorkflow.project)
            # self.assertIsNotNone(project)
