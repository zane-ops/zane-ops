from typing import cast
from django.urls import reverse
from rest_framework import status
from zane_api.utils import jprint
from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase


DUMMY_PRIVATE_IP = "192.168.1.125"


class CreateSwarmNodeViewTests(AuthAPITestCase):
    def test_create_node_successful(self):
        self.loginUser()
        response = self.client.post(
            reverse("swarm:nodes.list"),
            data={
                "private_ip": DUMMY_PRIVATE_IP,
                "role": SwarmNode.Role.WORKER,
                "is_app_server": True,
                "is_build_server": False,
                "ssh_port": 2222,
            },
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        created_node = cast(
            SwarmNode, SwarmNode.objects.filter(private_ip=DUMMY_PRIVATE_IP).first()
        )
        self.assertIsNotNone(created_node)
        self.assertEqual(SwarmNode.Status.CREATED, created_node.status)
        self.assertEqual(SwarmNode.Role.WORKER, created_node.role)
        self.assertEqual(2222, created_node.ssh_port)

    async def test_provision_node(self):
        pass
