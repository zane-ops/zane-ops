from typing import cast
from .base import AuthAPITestCase
from ..models import DeploymentChange, SharedVolume, Service
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

    def test_update_shared_volume_changes(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="shared-data",
            container_path="/data",
        )

        _, service2 = self.create_redis_docker_service(slug="worker")
        shared_vol = SharedVolume.objects.create(
            volume=v,
            reader=service2,
            container_path="/app/data",
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "UPDATE",
            "item_id": shared_vol.id,
            "new_value": {
                "volume_id": v.id,
                "container_path": "/app/shared-data",
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
        self.assertEqual("UPDATE", shared_volumes_change.type)
        new_value = cast(dict, shared_volumes_change.new_value)
        self.assertEqual("/app/shared-data", new_value["container_path"])

    def test_delete_shared_volume_changes(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="temp-volume",
            container_path="/tmp",
        )

        _, service2 = self.create_redis_docker_service(slug="consumer")
        shared_vol = SharedVolume.objects.create(
            volume=v,
            reader=service2,
            container_path="/tmp/shared",
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "DELETE",
            "item_id": shared_vol.id,
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
        self.assertEqual("DELETE", shared_volumes_change.type)
        self.assertEqual(shared_vol.id, shared_volumes_change.item_id)

    def test_cannot_share_own_volume(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="own-volume",
            container_path="/data",
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v.id,
                "container_path": "/shared/data",
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
        errors = response.json()["errors"]
        self.assertIn("volume_id", str(errors))

    def test_cannot_share_host_path_volume(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="host-volume",
            container_path="/etc/localtime",
            host_path="/etc/localtime",
        )

        _, service2 = self.create_redis_docker_service(slug="consumer")

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v.id,
                "container_path": "/app/localtime",
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        errors = response.json()["errors"]
        self.assertIn("volume_id", str(errors))
        self.assertIn("host path", str(errors))

    def test_cannot_share_volume_from_different_environment(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="prod-volume",
            container_path="/data",
        )

        # Create service in different environment
        p.environments.create(name="staging")

        create_service_payload = {
            "slug": "staging-service",
            "image": "valkey/valkey:7.2-alpine",
        }
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "staging",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service2 = Service.objects.get(slug="staging-service")

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v.id,
                "container_path": "/app/data",
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "staging",
                    "service_slug": service2.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        errors = response.json()["errors"]
        self.assertIn("environment", str(errors))

    def test_cannot_duplicate_container_path_with_owned_volume(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(
            name="shared-volume",
            container_path="/data",
        )

        _, service2 = self.create_redis_docker_service(slug="consumer")
        service2.volumes.create(
            name="own-volume",
            container_path="/app/data",
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v.id,
                "container_path": "/app/data",  # Conflicts with owned volume
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        errors = response.json()["errors"]
        self.assertIn("container_path", str(errors))

    def test_cannot_duplicate_container_path_with_shared_volume(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v1 = service.volumes.create(name="volume-1", container_path="/data1")
        v2 = service.volumes.create(name="volume-2", container_path="/data2")

        _, service2 = self.create_redis_docker_service(slug="consumer")
        SharedVolume.objects.create(
            volume=v1,
            reader=service2,
            container_path="/app/shared",
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v2.id,
                "container_path": "/app/shared",  # Conflicts with existing shared volume
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        errors = response.json()["errors"]
        self.assertIn("container_path", str(errors))

    def test_cannot_share_same_volume_twice(self):
        self.loginUser()

        p, service = self.create_redis_docker_service()
        v = service.volumes.create(name="shared-vol", container_path="/data")

        _, service2 = self.create_redis_docker_service(slug="consumer")
        SharedVolume.objects.create(
            volume=v,
            reader=service2,
            container_path="/app/data1",
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.SHARED_VOLUMES,
            "type": "ADD",
            "new_value": {
                "volume_id": v.id,
                "container_path": "/app/data2",  # Different path but same volume
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        errors = response.json()["errors"]
        self.assertIn("volume", str(errors))

    def test_apply_shared_volume_changes(self):
        self.loginUser()

        p, service = self.create_caddy_docker_service()
        v1 = service.volumes.create(name="volume-to-share", container_path="/data")
        v2 = service.volumes.create(name="volume-to-share-2", container_path="/cache")

        _, service2 = self.create_caddy_docker_service(slug="consumer")
        shared_to_delete = SharedVolume.objects.create(
            volume=v1,
            reader=service2,
            container_path="/app/temp",
        )
        shared_to_update = SharedVolume.objects.create(
            volume=v2,
            reader=service2,
            container_path="/app/cache",
        )

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service2,
                ),
                # Delete first to avoid conflicts with the unique constraint
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SHARED_VOLUMES,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=shared_to_delete.id,
                    service=service2,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SHARED_VOLUMES,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=shared_to_update.id,
                    new_value={
                        "volume_id": v2.id,
                        "container_path": "/app/updated-cache",
                    },
                    service=service2,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SHARED_VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "volume_id": v1.id,
                        "container_path": "/app/data",
                    },
                    service=service2,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service2.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        updated_service = Service.objects.get(slug=service2.slug)
        self.assertEqual(2, updated_service.shared_volumes.count())

        # Check new shared volume was added
        new_shared = cast(
            SharedVolume,
            updated_service.shared_volumes.filter(container_path="/app/data").first(),
        )
        self.assertIsNotNone(new_shared)
        self.assertEqual(v1.id, new_shared.volume.id)

        # Check shared volume was updated
        updated_shared = cast(
            SharedVolume,
            updated_service.shared_volumes.filter(
                container_path="/app/updated-cache"
            ).first(),
        )
        self.assertIsNotNone(updated_shared)
        self.assertEqual(v2.id, updated_shared.volume.id)

        # Check shared volume was deleted
        self.assertFalse(
            updated_service.shared_volumes.filter(id=shared_to_delete.id).exists()
        )

    def test_list_available_volumes(self):
        self.loginUser()

        p, service1 = self.create_redis_docker_service(slug="service1")
        v1 = service1.volumes.create(name="volume1", container_path="/data1")
        v2 = service1.volumes.create(name="volume2", container_path="/data2")

        # Host path volume should not be listed
        service1.volumes.create(
            name="host-vol", container_path="/etc/localtime", host_path="/etc/localtime"
        )

        _, service2 = self.create_redis_docker_service(slug="service2")

        response = self.client.get(
            reverse(
                "zane_api:services.volumes.available",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": service2.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        volumes = response.json()
        self.assertEqual(2, len(volumes))

        volume_ids = [vol["id"] for vol in volumes]
        self.assertIn(v1.id, volume_ids)
        self.assertIn(v2.id, volume_ids)

        # Verify service info is included
        for vol in volumes:
            self.assertIn("service", vol)
            self.assertEqual(service1.id, vol["service"]["id"])
            self.assertEqual(service1.slug, vol["service"]["slug"])

    def test_cannot_delete_volume_if_referenced_in_pending_shared_volume_change(self):
        pass

    def test_cannot_rollback_deployment_if_would_break_shared_volume_reference(self):
        # if by redeploying a service, it would remove one of its volume that is referenced in a shared volume
        pass
