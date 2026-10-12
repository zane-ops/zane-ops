from django.urls import reverse
from rest_framework import status

from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint


class UpdateSwarmNodeRolesViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.main_node = SwarmNode.objects.create(
            hostname="zane-main",
            swarm_node_id="swarm-main",
            private_ip="10.0.0.1",
            swarm_role=SwarmNode.Role.MANAGER,
            status=SwarmNode.Status.ACTIVE,
            is_initial_install_server=True,
            cluster_roles=[
                SwarmNode.ClusterRole.APP_SERVER,
                SwarmNode.ClusterRole.BUILD_SERVER,
            ],
        )
        self.node = SwarmNode.objects.create(
            hostname="zane-worker",
            swarm_node_id="swarm-worker",
            private_ip="10.0.0.2",
            swarm_role=SwarmNode.Role.WORKER,
            status=SwarmNode.Status.ACTIVE,
            cluster_roles=[SwarmNode.ClusterRole.APP_SERVER],
        )
        self.VALID_PAYLOAD = {
            "swarm_role": SwarmNode.Role.MANAGER,
            "cluster_roles": [
                SwarmNode.ClusterRole.APP_SERVER,
                SwarmNode.ClusterRole.BUILD_SERVER,
            ],
        }

    def update_roles(self, node_id: str, data: dict):
        return self.client.put(
            reverse("swarm:node.update_roles", kwargs={"id": node_id}),
            data=data,
            content_type="application/json",
        )

    def assertNodeUnchanged(self, node: SwarmNode):
        swarm_role = node.swarm_role
        cluster_roles = node.cluster_roles
        node.refresh_from_db()
        self.assertEqual(swarm_role, node.swarm_role)
        self.assertEqual(sorted(cluster_roles), sorted(node.cluster_roles))

    def test_update_roles_requires_instance_owner(self):
        response = self.update_roles(self.node.id, self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_update_roles_non_existent_node(self):
        self.loginUser()
        response = self.update_roles("node_doesnotexist", self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_update_roles_successful(self):
        self.loginUser()
        response = self.update_roles(self.node.id, self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_update_roles_does_not_save_the_node_before_the_workflow(self):
        """
        The roles are saved by the workflow once the swarm node is updated,
        not by the API
        """
        self.loginUser()
        response = self.update_roles(self.node.id, self.VALID_PAYLOAD)
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        self.assertNodeUnchanged(self.node)

    def test_update_roles_requires_swarm_role_and_cluster_roles(self):
        self.loginUser()
        response = self.update_roles(self.node.id, {})
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "swarm_role"))
        self.assertIsNotNone(self.get_error_from_response(response, "cluster_roles"))

    def test_update_roles_with_invalid_swarm_role(self):
        self.loginUser()
        response = self.update_roles(
            self.node.id,
            {**self.VALID_PAYLOAD, "swarm_role": "SUPERVISOR"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "swarm_role"))

    def test_update_roles_with_invalid_cluster_role(self):
        self.loginUser()
        response = self.update_roles(
            self.node.id,
            {**self.VALID_PAYLOAD, "cluster_roles": ["DATABASE_SERVER"]},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "cluster_roles"))

    def test_update_roles_requires_at_least_one_cluster_role(self):
        self.loginUser()
        response = self.update_roles(
            self.node.id,
            {**self.VALID_PAYLOAD, "cluster_roles": []},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "cluster_roles"))
        self.assertNodeUnchanged(self.node)

    def test_main_server_can_have_empty_cluster_roles(self):
        self.loginUser()
        # another node keeps both roles
        self.node.cluster_roles = [
            SwarmNode.ClusterRole.APP_SERVER,
            SwarmNode.ClusterRole.BUILD_SERVER,
        ]
        self.node.save()
        response = self.update_roles(
            self.main_node.id,
            {"swarm_role": SwarmNode.Role.MANAGER, "cluster_roles": []},
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_main_server_cannot_have_empty_cluster_roles_if_it_is_the_last_one_with_a_role(
        self,
    ):
        self.loginUser()
        # the other node only has the app role, the main server is the last build server
        response = self.update_roles(
            self.main_node.id,
            {"swarm_role": SwarmNode.Role.MANAGER, "cluster_roles": []},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertNodeUnchanged(self.main_node)

    def test_cannot_demote_the_main_server_to_worker(self):
        self.loginUser()
        response = self.update_roles(
            self.main_node.id,
            {**self.VALID_PAYLOAD, "swarm_role": SwarmNode.Role.WORKER},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertNodeUnchanged(self.main_node)

    def test_can_update_cluster_roles_of_the_main_server(self):
        self.loginUser()
        # another node keeps the build role
        self.node.cluster_roles = [  # type: ignore
            SwarmNode.ClusterRole.APP_SERVER,
            SwarmNode.ClusterRole.BUILD_SERVER,
        ]
        self.node.save()
        response = self.update_roles(
            self.main_node.id,
            {
                "swarm_role": SwarmNode.Role.MANAGER,
                "cluster_roles": [SwarmNode.ClusterRole.APP_SERVER],
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_cannot_update_roles_of_node_not_in_the_cluster(self):
        self.loginUser()
        for node_status in [
            SwarmNode.Status.CREATED,
            SwarmNode.Status.PROVISIONING,
            SwarmNode.Status.FAILED,
            SwarmNode.Status.REMOVED,
        ]:
            with self.subTest(status=node_status):
                self.node.status = node_status
                self.node.save()
                response = self.update_roles(self.node.id, self.VALID_PAYLOAD)
                jprint(response.json())
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.assertNodeUnchanged(self.node)

    def test_cannot_update_roles_of_node_without_swarm_node_id(self):
        self.loginUser()
        self.node.swarm_node_id = None
        self.node.save()
        response = self.update_roles(self.node.id, self.VALID_PAYLOAD)
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_can_update_roles_of_node_in_any_cluster_status(self):
        self.loginUser()
        for node_status in [
            SwarmNode.Status.ACTIVE,
            SwarmNode.Status.DOWN,
            SwarmNode.Status.UNHEALTHY,
            SwarmNode.Status.PAUSED,
            SwarmNode.Status.DRAINED,
        ]:
            with self.subTest(status=node_status):
                self.node.status = node_status
                self.node.save()
                response = self.update_roles(self.node.id, self.VALID_PAYLOAD)
                self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_cannot_remove_the_last_build_server(self):
        self.loginUser()
        response = self.update_roles(
            self.main_node.id,
            {
                "swarm_role": SwarmNode.Role.MANAGER,
                "cluster_roles": [SwarmNode.ClusterRole.APP_SERVER],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertNodeUnchanged(self.main_node)

    def test_cannot_remove_the_last_app_server(self):
        self.loginUser()
        self.node.cluster_roles = [SwarmNode.ClusterRole.BUILD_SERVER]  # type: ignore
        self.node.save()
        response = self.update_roles(
            self.main_node.id,
            {
                "swarm_role": SwarmNode.Role.MANAGER,
                "cluster_roles": [SwarmNode.ClusterRole.BUILD_SERVER],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertNodeUnchanged(self.main_node)

    def test_can_remove_a_role_if_another_node_in_the_cluster_has_it(self):
        self.loginUser()
        self.node.cluster_roles = [SwarmNode.ClusterRole.BUILD_SERVER]
        self.node.save()
        response = self.update_roles(
            self.main_node.id,
            {
                "swarm_role": SwarmNode.Role.MANAGER,
                "cluster_roles": [SwarmNode.ClusterRole.APP_SERVER],
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_nodes_not_in_the_cluster_do_not_count_as_build_or_app_servers(self):
        self.loginUser()
        for index, node_status in enumerate(
            [
                SwarmNode.Status.CREATED,
                SwarmNode.Status.PROVISIONING,
                SwarmNode.Status.FAILED,
                SwarmNode.Status.REMOVED,
            ]
        ):
            with self.subTest(status=node_status):
                SwarmNode.objects.create(
                    private_ip=f"10.0.1.{index + 1}",
                    swarm_role=SwarmNode.Role.WORKER,
                    status=node_status,
                    cluster_roles=[SwarmNode.ClusterRole.BUILD_SERVER],
                )
                response = self.update_roles(
                    self.main_node.id,
                    {
                        "swarm_role": SwarmNode.Role.MANAGER,
                        "cluster_roles": [SwarmNode.ClusterRole.APP_SERVER],
                    },
                )
                jprint(response.json())
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
