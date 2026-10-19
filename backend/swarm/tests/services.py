from typing import cast

from django.urls import reverse
from rest_framework import status

from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint, generate_random_chars
from zane_api.models import DeploymentChange, Service


class ServiceDeploymentViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.main_node = SwarmNode.objects.create(
            hostname="zane-main",
            private_ip="10.0.0.1",
            swarm_node_id=generate_random_chars(25),
            swarm_role=SwarmNode.Role.MANAGER,
            status=SwarmNode.Status.ACTIVE,
            is_initial_install_server=True,
            cluster_roles=[
                SwarmNode.ClusterRole.APP_SERVER,
                SwarmNode.ClusterRole.BUILD_SERVER,
            ],
        )
        self.node = SwarmNode.objects.create(
            private_ip="10.0.0.2",
            hostname="zane-another",
            swarm_node_id=generate_random_chars(25),
            swarm_role=SwarmNode.Role.WORKER,
            status=SwarmNode.Status.CREATED,
            cluster_roles=[SwarmNode.ClusterRole.APP_SERVER],
        )

    def test_validate_existing_swarm_node_id(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": "UPDATE",
            "new_value": {
                "strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server_id": "doesnotexists",
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        jprint(response.json())
        self.assertIsNotNone(
            self.get_error_from_response(response, "new_value.deployment_server_id")
        )

    def test_validate_server_is_active(self):
        p, service = self.create_and_deploy_caddy_docker_service()
        self.node.swarm_node_id = None
        self.node.save()

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": "UPDATE",
            "new_value": {
                "strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server_id": self.node.id,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        jprint(response.json())
        self.assertIsNotNone(
            self.get_error_from_response(response, "new_value.deployment_server_id")
        )

    def test_validate_server_is_app_server(self):
        p, service = self.create_and_deploy_caddy_docker_service()
        self.node.cluster_roles = [SwarmNode.ClusterRole.BUILD_SERVER]  # type: ignore
        self.node.save()

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": "UPDATE",
            "new_value": {
                "strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server_id": self.node.id,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        jprint(response.json())
        self.assertIsNotNone(
            self.get_error_from_response(response, "new_value.deployment_server_id")
        )

    def test_update_deployment_strategy_add_change_to_service(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": "UPDATE",
            "new_value": {
                "strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server_id": self.node.id,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        jprint(response.json())

        self.assertEqual(1, service.unapplied_changes.count())
        change: DeploymentChange = cast(
            DeploymentChange,
            DeploymentChange.objects.filter(
                service__slug=service.slug,
                field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            ).first(),
        )
        self.assertEqual(
            {
                "strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server": {
                    "id": self.node.id,
                    "swarm_node_id": self.node.swarm_node_id,
                    "hostname": self.node.hostname,
                },
            },
            change.new_value,
        )
