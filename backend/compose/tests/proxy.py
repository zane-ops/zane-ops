from typing import cast

from .stacks import ComposeStackAPITestBase
from .fixtures import DOCKER_COMPOSE_WEB_SERVICE
from django.urls import reverse
from rest_framework import status
from zane_api.utils import jprint


class ComposeProxyViewTestCase(ComposeStackAPITestBase):
    async def test_check_certificate_for_compose_stack(self):
        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE
        )

        self.assertIsNotNone(stack.urls)
        response = await self.async_client.get(
            reverse(
                "zane_api:proxy.check_certificates",
                query={"domain": cast(dict, stack.urls)["web"][0]["domain"]},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
