from typing import cast
from .base import AuthAPITestCase
from ..models import DeploymentChange
from django.urls import reverse
from rest_framework import status
from ..utils import jprint


class SharedVolumesViewTests(AuthAPITestCase):
    def test_add_shared_volumes_changes(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="caddyfile",
            container_path="/etc/caddy/Caddyfile",
        )

        _, service2 = self.create_redis_docker_service(slug="valkey")

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v.id,
                "container_path": "/var/www/html/website.caddy",
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service2.slug,
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        shared_volumes_change = cast(
            DeploymentChange,
            service2.unapplied_changes.filter(
                field=DeploymentChange.ChangeField.SHARED_VOLUMES
            ).first(),
        )
        self.assertIsNotNone(shared_volumes_change)
        new_value = cast(dict, shared_volumes_change.new_value)
        self.assertEqual(v.id, new_value["volume_id"])
        self.assertEqual("/var/www/html/website.caddy", new_value["container_path"])
