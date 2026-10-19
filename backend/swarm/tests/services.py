from typing import cast

from django.urls import reverse
from rest_framework import status

from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint, generate_random_chars
from zane_api.models import DeploymentChange, Service, Volume


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
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server_id": "doesnotexist",
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
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
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
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
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
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
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
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server": {
                    "id": self.node.id,
                    "swarm_node_id": self.node.swarm_node_id,
                    "hostname": self.node.hostname,
                },
            },
            change.new_value,
        )

    def test_validate_deployment_strategy_specific_require_server_id(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": "UPDATE",
            "new_value": {
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server_id": None,
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

    def test_validate_deployment_strategy_any_ignores_server_id(self):
        p, service = self.create_and_deploy_caddy_docker_service()
        # Update to make sure the change is computed
        service.deployment_strategy = Service.DeploymentStrategy.SPECIFIC_SERVER
        service.deployment_server = self.main_node
        service.save()

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": "UPDATE",
            "new_value": {
                "deployment_strategy": Service.DeploymentStrategy.ANY_APP_SERVER,
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
                "deployment_strategy": Service.DeploymentStrategy.ANY_APP_SERVER,
                "deployment_server": None,
            },
            change.new_value,
        )

    def test_validate_deployment_strategy_cannot_be_changed_to_any_if_service_has_a_volume(
        self,
    ):
        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                )
            ]
        )
        self.assertEqual(
            Service.DeploymentStrategy.SPECIFIC_SERVER, service.deployment_strategy
        )
        self.assertIsNotNone(service.deployment_server)

        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "deployment_strategy": Service.DeploymentStrategy.ANY_APP_SERVER,
                "deployment_server_id": None,
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
            self.get_error_from_response(response, "new_value.deployment_strategy")
        )

    def test_service_with_volume_also_add_deployment_strategy_change_when_applied(self):
        p, service = self.create_redis_docker_service()
        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "name": "zane-logs",
                "container_path": "/etc/logs/zane",
            },
        }

        # Add changes
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

        # Deploy service
        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        jprint(response.json())

        service.refresh_from_db()

        self.assertEqual(
            Service.DeploymentStrategy.SPECIFIC_SERVER, service.deployment_strategy
        )
        self.assertIsNotNone(service.deployment_server)

    def test_apply_deployment_strategy_change_to_service(self):
        p, service = self.create_caddy_docker_service()

        # Add changes
        changes_payload = {
            "field": DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
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

        # Deploy service
        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        jprint(response.json())

        service.refresh_from_db()

        self.assertEqual(
            Service.DeploymentStrategy.SPECIFIC_SERVER, service.deployment_strategy
        )
        self.assertEqual(self.node, service.deployment_server)
