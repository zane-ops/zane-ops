from django.urls import reverse
from rest_framework import status

from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint


class ProvisionSwarmNodeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.main_node = SwarmNode.objects.create(
            hostname="zane-main",
            private_ip="10.0.0.1",
            swarm_role=SwarmNode.Role.MANAGER,
            status=SwarmNode.Status.ACTIVE,
            is_initial_install_server=True,
        )
        self.node = SwarmNode.objects.create(
            private_ip="10.0.0.2",
            swarm_role=SwarmNode.Role.WORKER,
            status=SwarmNode.Status.CREATED,
            cluster_roles=[SwarmNode.ClusterRole.APP_SERVER],
        )
        self.main_key = self.create_ssh_key(self.main_node, user="root")
        self.node_key = self.create_ssh_key(self.node, user="root")

    def provision(self, node_id: str, data: dict):
        return self.client.post(
            reverse("swarm:node.provision", kwargs={"id": node_id}),
            data=data,
        )

    def test_provision_requires_instance_owner(self):
        response = self.provision(
            self.node.id,
            {
                "target_ssh_key_id": self.node_key.id,
                "main_ssh_key_id": self.main_key.id,
            },
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
        self.node.refresh_from_db()
        self.assertEqual(SwarmNode.Status.CREATED, self.node.status)

    def test_provision_non_existent_node(self):
        self.loginUser()
        response = self.provision(
            "node_doesnotexist",
            {
                "target_ssh_key_id": self.node_key.id,
                "main_ssh_key_id": self.main_key.id,
            },
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_provision_requires_both_ssh_keys(self):
        self.loginUser()
        response = self.provision(self.node.id, {})
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "target_ssh_key_id")
        )
        self.assertIsNotNone(self.get_error_from_response(response, "main_ssh_key_id"))
        self.node.refresh_from_db()
        self.assertEqual(SwarmNode.Status.CREATED, self.node.status)

    def test_provision_with_non_existent_target_key(self):
        self.loginUser()
        response = self.provision(
            self.node.id,
            {"target_ssh_key_id": 9999, "main_ssh_key_id": self.main_key.id},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "target_ssh_key_id")
        )

    def test_provision_with_target_key_from_another_node(self):
        self.loginUser()
        response = self.provision(
            self.node.id,
            {
                "target_ssh_key_id": self.main_key.id,
                "main_ssh_key_id": self.main_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "target_ssh_key_id")
        )

    def test_provision_with_main_key_from_another_node(self):
        self.loginUser()
        response = self.provision(
            self.node.id,
            {
                "target_ssh_key_id": self.node_key.id,
                "main_ssh_key_id": self.node_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "main_ssh_key_id"))

    def test_provision_with_non_root_target_key(self):
        self.loginUser()
        non_root_key = self.create_ssh_key(self.node, user="ubuntu", name="ubuntu")
        response = self.provision(
            self.node.id,
            {
                "target_ssh_key_id": non_root_key.id,
                "main_ssh_key_id": self.main_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "target_ssh_key_id")
        )

    def test_provision_with_non_root_main_key(self):
        self.loginUser()
        non_root_key = self.create_ssh_key(self.main_node, user="ubuntu", name="ubuntu")
        response = self.provision(
            self.node.id,
            {
                "target_ssh_key_id": self.node_key.id,
                "main_ssh_key_id": non_root_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "main_ssh_key_id"))

    def test_cannot_provision_the_main_server(self):
        self.loginUser()
        response = self.provision(
            self.main_node.id,
            {
                "target_ssh_key_id": self.main_key.id,
                "main_ssh_key_id": self.main_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.main_node.refresh_from_db()
        self.assertEqual(SwarmNode.Status.ACTIVE, self.main_node.status)

    def test_cannot_provision_node_already_in_the_cluster(self):
        self.loginUser()
        for node_status in [
            SwarmNode.Status.PROVISIONING,
            SwarmNode.Status.ACTIVE,
            SwarmNode.Status.DOWN,
            SwarmNode.Status.PAUSED,
            SwarmNode.Status.DRAINED,
        ]:
            with self.subTest(status=node_status):
                self.node.status = node_status
                self.node.save()
                response = self.provision(
                    self.node.id,
                    {
                        "target_ssh_key_id": self.node_key.id,
                        "main_ssh_key_id": self.main_key.id,
                    },
                )
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.node.refresh_from_db()
                self.assertEqual(node_status, self.node.status)
