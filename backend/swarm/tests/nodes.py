from typing import cast
from django.urls import reverse
from rest_framework import status
from zane_api.utils import jprint
from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase


DUMMY_PRIVATE_IP = "192.168.1.125"


class CreateSwarmNodeViewTests(AuthAPITestCase):
    def create_node(self, data: dict):
        return self.client.post(
            reverse("swarm:nodes.list"),
            data=data,
        )

    def test_create_node_successful(self):
        self.loginUser()
        response = self.create_node(
            {
                "private_ip": DUMMY_PRIVATE_IP,
                "swarm_role": SwarmNode.Role.WORKER,
                "cluster_roles": [SwarmNode.ClusterRole.APP_SERVER],
                "ssh_port": 2222,
            }
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_node = cast(
            SwarmNode, SwarmNode.objects.filter(private_ip=DUMMY_PRIVATE_IP).first()
        )
        self.assertIsNotNone(created_node)
        self.assertEqual(SwarmNode.Status.CREATED, created_node.status)
        self.assertEqual(SwarmNode.Role.WORKER, created_node.swarm_role)
        self.assertEqual([SwarmNode.ClusterRole.APP_SERVER], created_node.cluster_roles)
        self.assertEqual(2222, created_node.ssh_port)
        self.assertFalse(created_node.is_initial_install_server)

    def test_create_node_deduplicates_cluster_roles(self):
        self.loginUser()
        response = self.create_node(
            {
                "private_ip": DUMMY_PRIVATE_IP,
                "swarm_role": SwarmNode.Role.WORKER,
                "cluster_roles": [
                    SwarmNode.ClusterRole.APP_SERVER,
                    SwarmNode.ClusterRole.BUILD_SERVER,
                    SwarmNode.ClusterRole.APP_SERVER,
                ],
            }
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_node = SwarmNode.objects.get(private_ip=DUMMY_PRIVATE_IP)
        self.assertEqual(
            {SwarmNode.ClusterRole.APP_SERVER, SwarmNode.ClusterRole.BUILD_SERVER},
            set(created_node.cluster_roles),
        )
        self.assertEqual(2, len(created_node.cluster_roles))

    def test_create_node_requires_at_least_one_cluster_role(self):
        self.loginUser()
        response = self.create_node(
            {
                "private_ip": DUMMY_PRIVATE_IP,
                "swarm_role": SwarmNode.Role.WORKER,
                "cluster_roles": [],
            }
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(0, SwarmNode.objects.count())

    def test_create_node_without_cluster_roles(self):
        self.loginUser()
        response = self.create_node(
            {
                "private_ip": DUMMY_PRIVATE_IP,
                "swarm_role": SwarmNode.Role.WORKER,
            }
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(0, SwarmNode.objects.count())

    def test_create_node_ignores_read_only_fields(self):
        self.loginUser()
        response = self.create_node(
            {
                "private_ip": DUMMY_PRIVATE_IP,
                "swarm_role": SwarmNode.Role.WORKER,
                "cluster_roles": [SwarmNode.ClusterRole.APP_SERVER],
                "status": SwarmNode.Status.ACTIVE,
                "is_initial_install_server": True,
                "swarm_node_id": "swarm-fake",
                "hostname": "zane-fake",
            }
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_node = SwarmNode.objects.get(private_ip=DUMMY_PRIVATE_IP)
        self.assertEqual(SwarmNode.Status.CREATED, created_node.status)
        self.assertFalse(created_node.is_initial_install_server)
        self.assertIsNone(created_node.swarm_node_id)
        self.assertIsNone(created_node.hostname)
