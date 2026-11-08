from typing import cast

from .base import AuthAPITestCase
from ..models import DeploymentChange
from django.urls import reverse
from rest_framework import status
from ..utils import jprint
from django.conf import settings
import responses


class ServiceReplicasViewTests(AuthAPITestCase):
    def test_request_add_service_replicas_change(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.REPLICAS,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "replicas": 2,
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
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service_replicas_change = cast(
            DeploymentChange,
            service.unapplied_changes.filter(
                field=DeploymentChange.ChangeField.REPLICAS
            ).first(),
        )
        self.assertIsNotNone(service_replicas_change)
        new_value = cast(dict, service_replicas_change.new_value)
        self.assertEqual(2, new_value["replicas"])

    def test_apply_service_replica_change(self):
        self.loginUser()

        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.REPLICAS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "replicas": 2,
                    },
                    old_value={"replicas": 1},
                )
            ]
        )

        self.assertEqual(2, service.replicas)

    async def test_deploy_service_with_replicas(self):
        await self.aLoginUser()

        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.REPLICAS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "replicas": 2,
                    },
                    old_value={"replicas": 1},
                )
            ]
        )

        deployment = await service.deployments.afirst()

        svc = self.fake_docker_client.get_deployment_service(deployment)  # type: ignore
        self.assertIsNotNone(svc)
        self.assertEqual(2, svc.replicas)  # type: ignore

    def test_rollback_service_replicas(self):
        self.loginUser()

        # First deployment
        p, service = self.create_and_deploy_redis_docker_service()

        DeploymentChange.objects.create(
            field=DeploymentChange.ChangeField.REPLICAS,
            type=DeploymentChange.ChangeType.UPDATE,
            new_value={
                "replicas": 2,
            },
            old_value={"replicas": 1},
            service=service,
        )

        # Second deployment after scaling
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        self.assertEqual(service.replicas, 2)

        # Rollback to first deployment
        first_deployment = service.deployments.earliest("queued_at")
        response = self.client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": first_deployment.hash,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        service.refresh_from_db()
        self.assertEqual(service.replicas, 1)
