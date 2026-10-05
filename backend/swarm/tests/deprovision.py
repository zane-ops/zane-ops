from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status

from swarm.models import SSHKey, SwarmNode
from temporal.shared import ClusterSwarmNodePair
from temporal.workflows import RemoveSwarmNodeFromClusterWorkflow
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint


class DeprovisionSwarmNodeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.main_node = SwarmNode.objects.create(
            hostname="zane-main",
            swarm_node_id="swarm-main",
            private_ip="10.0.0.1",
            swarm_role=SwarmNode.Role.MANAGER,
            status=SwarmNode.Status.ACTIVE,
            is_initial_install_server=True,
        )
        self.node = SwarmNode.objects.create(
            hostname="zane-worker",
            swarm_node_id="swarm-worker",
            private_ip="10.0.0.2",
            swarm_role=SwarmNode.Role.WORKER,
            status=SwarmNode.Status.ACTIVE,
            cluster_roles=[SwarmNode.ClusterRole.APP_SERVER],
        )
        self.main_key = self.create_ssh_key(self.main_node, user="root")
        self.node_key = self.create_ssh_key(self.node, user="root")
        self.VALID_PAYLOAD = {
            "target_ssh_key_id": self.node_key.id,
            "main_ssh_key_id": self.main_key.id,
        }

    def deprovision(self, node_id: str, data: dict):
        return self.client.put(
            reverse("swarm:node.deprovision", kwargs={"id": node_id}),
            data=data,
        )

    def test_deprovision_requires_instance_owner(self):
        response = self.deprovision(self.node.id, self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_deprovision_non_existent_node(self):
        self.loginUser()
        response = self.deprovision("node_doesnotexist", self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_deprovision_successful(self):
        self.loginUser()
        response = self.deprovision(self.node.id, self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_deprovision_requires_both_ssh_keys(self):
        self.loginUser()
        response = self.deprovision(self.node.id, {})
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "target_ssh_key_id")
        )
        self.assertIsNotNone(self.get_error_from_response(response, "main_ssh_key_id"))

    def test_deprovision_with_target_key_from_another_node(self):
        self.loginUser()
        response = self.deprovision(
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

    def test_deprovision_with_main_key_from_another_node(self):
        self.loginUser()
        response = self.deprovision(
            self.node.id,
            {
                "target_ssh_key_id": self.node_key.id,
                "main_ssh_key_id": self.node_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "main_ssh_key_id"))

    def test_deprovision_with_non_root_keys(self):
        self.loginUser()
        non_root_target = self.create_ssh_key(self.node, user="ubuntu", name="ubuntu")
        non_root_main = self.create_ssh_key(
            self.main_node, user="ubuntu", name="ubuntu"
        )
        response = self.deprovision(
            self.node.id,
            {
                "target_ssh_key_id": non_root_target.id,
                "main_ssh_key_id": non_root_main.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "target_ssh_key_id")
        )
        self.assertIsNotNone(self.get_error_from_response(response, "main_ssh_key_id"))

    def test_cannot_deprovision_the_main_server(self):
        self.loginUser()
        response = self.deprovision(
            self.main_node.id,
            {
                "target_ssh_key_id": self.main_key.id,
                "main_ssh_key_id": self.main_key.id,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_cannot_deprovision_node_not_in_the_cluster(self):
        self.loginUser()
        for node_status in [
            SwarmNode.Status.CREATED,
            SwarmNode.Status.FAILED,
            SwarmNode.Status.REMOVED,
            SwarmNode.Status.PROVISIONING,
        ]:
            with self.subTest(status=node_status):
                self.node.status = node_status
                self.node.save()
                response = self.deprovision(self.node.id, self.VALID_PAYLOAD)
                jprint(response.json())
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.node.refresh_from_db()
                self.assertEqual(node_status, self.node.status)

    def test_can_deprovision_node_in_any_cluster_status(self):
        self.loginUser()
        for node_status in [
            SwarmNode.Status.ACTIVE,
            SwarmNode.Status.DOWN,
            SwarmNode.Status.PAUSED,
            SwarmNode.Status.DRAINED,
        ]:
            with self.subTest(status=node_status):
                self.node.status = node_status
                self.node.save()
                response = self.deprovision(self.node.id, self.VALID_PAYLOAD)
                self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)


class DeleteSwarmNodeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.main_node = SwarmNode.objects.create(
            hostname="zane-main",
            swarm_node_id="swarm-main",
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
        self.node_key = self.create_ssh_key(self.node, user="root")

    def delete_node(self, node_id: str):
        return self.client.delete(
            reverse("swarm:node.detail", kwargs={"id": node_id}),
        )

    def test_delete_requires_instance_owner(self):
        response = self.delete_node(self.node.id)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
        self.assertTrue(SwarmNode.objects.filter(id=self.node.id).exists())

    def test_delete_non_existent_node(self):
        self.loginUser()
        response = self.delete_node("node_doesnotexist")
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_delete_node_not_in_the_cluster(self):
        self.loginUser()
        for index, node_status in enumerate(
            [
                SwarmNode.Status.CREATED,
                SwarmNode.Status.FAILED,
                SwarmNode.Status.REMOVED,
            ]
        ):
            with self.subTest(status=node_status):
                node = SwarmNode.objects.create(
                    private_ip=f"10.0.1.{index + 1}",
                    swarm_role=SwarmNode.Role.WORKER,
                    status=node_status,
                )
                response = self.delete_node(node.id)
                self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
                self.assertFalse(SwarmNode.objects.filter(id=node.id).exists())

    def test_delete_node_also_deletes_its_ssh_keys(self):
        self.loginUser()
        response = self.delete_node(self.node.id)
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertFalse(SwarmNode.objects.filter(id=self.node.id).exists())
        self.assertFalse(SSHKey.objects.filter(id=self.node_key.id).exists())

    def test_cannot_delete_the_main_server(self):
        self.loginUser()
        response = self.delete_node(self.main_node.id)
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertTrue(SwarmNode.objects.filter(id=self.main_node.id).exists())

    def test_cannot_delete_node_in_the_cluster(self):
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
                response = self.delete_node(self.node.id)
                jprint(response.json())
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.assertTrue(SwarmNode.objects.filter(id=self.node.id).exists())
