from typing import cast

from django.urls import reverse
from rest_framework import status

from swarm.models import SwarmNode
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint, generate_random_chars
from zane_api.models import DeploymentChange, Service, Volume, Deployment
from temporal.helpers import get_swarm_service_name_for_deployment
from django.conf import settings


class BaseDeployServerTest(AuthAPITestCase):
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
                SwarmNode.ClusterRole.DEPLOY_SERVER,
                SwarmNode.ClusterRole.BUILD_SERVER,
            ],
        )
        self.node = SwarmNode.objects.create(
            private_ip="10.0.0.2",
            hostname="zane-another",
            swarm_node_id=generate_random_chars(25),
            swarm_role=SwarmNode.Role.WORKER,
            status=SwarmNode.Status.CREATED,
            cluster_roles=[SwarmNode.ClusterRole.DEPLOY_SERVER],
        )


class ServiceDeploymentChangesViewTests(BaseDeployServerTest):
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
                },
            },
            change.new_value,
        )

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
                "deployment_strategy": Service.DeploymentStrategy.ANY_DEPLOY_SERVER,
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
                "deployment_strategy": Service.DeploymentStrategy.ANY_DEPLOY_SERVER,
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
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                        "deployment_server": {
                            "id": self.node.id,
                            "swarm_node_id": self.node.swarm_node_id,
                        },
                    },
                ),
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
                "deployment_strategy": Service.DeploymentStrategy.ANY_DEPLOY_SERVER,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "new_value.deployment_strategy")
        )

    def test_cannot_add_volume_change_if_deployment_strategy_is_any_app_server(self):
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
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        self.assertEqual(
            0,
            service.changes.filter(
                field=DeploymentChange.ChangeField.VOLUMES,
            ).count(),
        )

    def test_can_add_volume_changes_if_deployment_strategy_is_specific_server(
        self,
    ):
        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                        "deployment_server": {
                            "id": self.node.id,
                            "swarm_node_id": self.node.swarm_node_id,
                        },
                    },
                ),
            ]
        )

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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            1,
            service.changes.filter(
                field=DeploymentChange.ChangeField.VOLUMES,
            ).count(),
        )

    def test_cannot_remove_deployment_strategy_change_if_service_still_has_volumes(
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
                ),
            ]
        )
        change = DeploymentChange.objects.create(
            service=service,
            field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            type=DeploymentChange.ChangeType.UPDATE,
            new_value={
                "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                "deployment_server": {
                    "id": self.node.id,
                    "swarm_node_id": self.node.swarm_node_id,
                },
            },
        )

        # Remoce changes
        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        jprint(response.json())

        self.assertEqual(
            1,
            service.changes.filter(
                field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            ).count(),
        )

    def test_cannot_remove_deployment_strategy_change_if_service_still_has_volume_changes(
        self,
    ):
        p, service = self.create_redis_docker_service()

        changes = DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                        "deployment_server": {
                            "id": self.node.id,
                            "swarm_node_id": self.node.swarm_node_id,
                        },
                    },
                ),
            ]
        )

        # Remoce changes
        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": changes[1].id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        jprint(response.json())

        self.assertEqual(
            1,
            service.changes.filter(
                field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            ).count(),
        )

    def test_can_remove_deployment_strategy_change_if_service_has_no_volumes(
        self,
    ):
        p, service = self.create_redis_docker_service()

        changes = DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                        "deployment_server": {
                            "id": self.node.id,
                            "swarm_node_id": self.node.swarm_node_id,
                        },
                    },
                ),
            ]
        )

        # Remoce changes
        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": changes[0].id,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            service.changes.filter(
                field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
            ).count(),
        )

    def test_cannot_cancel_volume_delete_if_service_deployment_strategy_is_any_deploy_server(
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
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                        "deployment_server": {
                            "id": self.node.id,
                            "swarm_node_id": self.node.swarm_node_id,
                        },
                    },
                ),
            ]
        )
        volume = cast(Volume, service.volumes.first())

        volume_change, _ = DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=volume.id,
                ),
                DeploymentChange(
                    service=service,
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.ANY_DEPLOY_SERVER,
                        "deployment_server": None,
                    },
                ),
            ]
        )

        # Cancelling the volume deletion would leave a volume on an unpinned service
        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": volume_change.id,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(
            1,
            service.unapplied_changes.filter(
                field=DeploymentChange.ChangeField.VOLUMES,
                type=DeploymentChange.ChangeType.DELETE,
            ).count(),
        )

    def test_cannot_add_volume_change_if_deployment_strategy_is_any_even_with_default_deploy_server(
        self,
    ):
        self.fail("Not implemented")


class DeployServicesToServerViewTests(BaseDeployServerTest):
    async def test_service_is_deployed_to_correct_server(self):
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.DEPLOYMENT_STRATEGY,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "deployment_strategy": Service.DeploymentStrategy.SPECIFIC_SERVER,
                        "deployment_server": {
                            "id": self.node.id,
                            "swarm_node_id": self.node.swarm_node_id,
                        },
                    },
                ),
            ]
        )

        dpl = cast(Deployment, await service.deployments.afirst())
        service = self.fake_docker_client.services_get(
            get_swarm_service_name_for_deployment(
                deployment_hash=dpl.hash,
                project_id=p.id,
                service_id=service.id,
            )
        )
        self.assertIsNotNone(service)

        expected_deploy_server_constraint = [f"node.id=={self.node.swarm_node_id}"]
        self.assertEqual(service.constraints, expected_deploy_server_constraint)

    async def test_service_is_deployed_with_any_server_strategy(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()
        dpl = cast(Deployment, await service.deployments.afirst())
        service = self.fake_docker_client.services_get(
            get_swarm_service_name_for_deployment(
                deployment_hash=dpl.hash,
                project_id=p.id,
                service_id=service.id,
            )
        )
        self.assertIsNotNone(service)
        expected_deploy_server_constraint = [
            f"node.labels.{settings.DEPLOY_SERVER_LABEL}==true"
        ]
        self.assertEqual(service.constraints, expected_deploy_server_constraint)

    async def test_service_use_default_project_deployment_server(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        p.default_deployment_server = self.node
        await p.asave()

        # Redeploy service
        response = await self.async_client.put(
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

        dpl = cast(Deployment, await service.deployments.afirst())
        service = self.fake_docker_client.services_get(
            get_swarm_service_name_for_deployment(
                deployment_hash=dpl.hash,
                project_id=p.id,
                service_id=service.id,
            )
        )
        self.assertIsNotNone(service)

        expected_deploy_server_constraint = [f"node.id=={self.node.swarm_node_id}"]
        self.assertEqual(service.constraints, expected_deploy_server_constraint)

    async def test_service_use_default_environment_deployment_server(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        env = await p.aproduction_env
        env.default_deployment_server = self.node
        await env.asave()

        # Redeploy service
        response = await self.async_client.put(
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

        dpl = cast(Deployment, await service.deployments.afirst())
        service = self.fake_docker_client.services_get(
            get_swarm_service_name_for_deployment(
                deployment_hash=dpl.hash,
                project_id=p.id,
                service_id=service.id,
            )
        )
        self.assertIsNotNone(service)

        expected_deploy_server_constraint = [f"node.id=={self.node.swarm_node_id}"]
        self.assertEqual(service.constraints, expected_deploy_server_constraint)

    async def test_prefer_environment_server_over_project_default_server(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        p.default_deployment_server = self.main_node
        await p.asave()

        env = await p.aproduction_env
        env.default_deployment_server = self.node
        await env.asave()

        # Redeploy service
        response = await self.async_client.put(
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

        dpl = cast(Deployment, await service.deployments.afirst())
        service = self.fake_docker_client.services_get(
            get_swarm_service_name_for_deployment(
                deployment_hash=dpl.hash,
                project_id=p.id,
                service_id=service.id,
            )
        )
        self.assertIsNotNone(service)

        expected_deploy_server_constraint = [f"node.id=={self.node.swarm_node_id}"]
        self.assertEqual(service.constraints, expected_deploy_server_constraint)

    async def test_prefer_service_default_server_over_default_deploy_server(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        p.default_deployment_server = self.main_node
        await p.asave()

        service.deployment_strategy = Service.DeploymentStrategy.SPECIFIC_SERVER
        service.deployment_server = self.node
        await service.asave()

        # Redeploy service
        response = await self.async_client.put(
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

        dpl = cast(Deployment, await service.deployments.afirst())
        service = self.fake_docker_client.services_get(
            get_swarm_service_name_for_deployment(
                deployment_hash=dpl.hash,
                project_id=p.id,
                service_id=service.id,
            )
        )
        self.assertIsNotNone(service)

        expected_deploy_server_constraint = [f"node.id=={self.node.swarm_node_id}"]
        self.assertEqual(service.constraints, expected_deploy_server_constraint)

    async def test_create_volume_in_deploy_server(self):
        self.fail("Not implemented")

    async def test_git_service_is_deployed_to_correct_server(self):
        self.fail("Not implemented")

    async def test_git_service_use_default_deployment_server(self):
        self.fail("Not implemented")


class UpdateProjectAndEnvDefaultDeployServerViewTests(BaseDeployServerTest):
    def test_validate_project_deploy_server_update_references_existing_deploy_server(
        self,
    ):
        self.fail("Not implemented")

    def test_validate_env_deploy_server_update_references_existing_deploy_server(self):
        self.fail("Not implemented")


class CloneEnvViewTests(BaseDeployServerTest):
    def test_clone_environment_clones_default_deploy_server(self):
        self.fail("Not implemented")


class SwarmNodeDeployServerViewTests(BaseDeployServerTest):
    def test_cannot_deprovision_server_that_is_used_as_a_deploy_server(self):
        self.fail("Not implemented")

    def test_cannot_deprovision_server_that_is_used_as_a_default_deploy_server(self):
        self.fail("Not implemented")

    def test_cannot_deprovision_server_that_is_referenced_in_deploy_server_pending_changes(
        self,
    ):
        self.fail("Not implemented")

    def test_cannot_delete_ssh_root_key_if_server_is_used_as_deploy_server(self):
        self.fail("Not implemented")

    def test_cannot_remove_deploy_server_role_to_server_if_still_used_as_a_deploy_server(
        self,
    ):
        self.fail("Not implemented")

    def test_cannot_remove_deploy_server_role_to_server_if_still_used_as_a_default_deploy_server(
        self,
    ):
        self.fail("Not implemented")

    def test_cannot_remove_deploy_server_role_to_server_if_referenced_in_deploy_server_pending_changes(
        self,
    ):
        self.fail("Not implemented")
