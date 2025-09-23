# type: ignore
from unittest.mock import patch, MagicMock, call
import requests
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import (
    Project,
    Deployment,
    Service,
    DeploymentChange,
    Volume,
    PortConfiguration,
    URL,
    HealthCheck,
    EnvVariable,
)
from ..serializers import ServiceSerializer
from temporal.activities import (
    get_swarm_service_name_for_deployment,
    ZaneProxyClient,
)


class DockerServiceDeploymentViewTests(AuthAPITestCase):
    def test_get_deployments_succesful(self):
        project, service = self.create_and_deploy_redis_docker_service()
        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data.get("results")))

    def test_filter_deployments_succesful(self):
        project, service = self.create_and_deploy_redis_docker_service()
        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
            + "?status=REMOVED"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(0, len(data.get("results")))

    def test_deployments_project_non_existing(self):
        project, service = self.create_and_deploy_redis_docker_service()
        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": "inexistent",
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_deployments_service_non_existing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_get_single_deployment_succesful(self):
        project, service = self.create_and_deploy_redis_docker_service()
        deployment: Deployment = service.deployments.first()
        response = self.client.get(
            reverse(
                "zane_api:services.deployment_single",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_single_deployment_deployment_non_existing(self):
        project, service = self.create_and_deploy_redis_docker_service()
        response = self.client.get(
            reverse(
                "zane_api:services.deployment_single",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": "dkr_dpl_hash1234",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_filter_deployments_invalid_page_return_empty_list(self):
        project, service = self.create_and_deploy_redis_docker_service()
        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
            + "?page=100"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(0, len(data.get("results")))


class DockerServiceDeploymentAddChangesViewTests(AuthAPITestCase):

    def test_create_service_with_image_creates_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: Service = Service.objects.filter(slug="cache-db").first()
        self.assertIsNotNone(created_service)
        change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(DeploymentChange.ChangeField.SOURCE, change.field)
        self.assertEqual(DeploymentChange.ChangeType.UPDATE, change.type)
        self.assertEqual(None, change.old_value)
        self.assertEqual({"image": "redis:alpine"}, change.new_value)

    def test_create_service_with_custom_registry_creates_credential_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
            },
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: Service = Service.objects.filter(slug="main-app").first()
        self.assertIsNotNone(created_service)
        self.assertEqual(
            1, DeploymentChange.objects.filter(service=created_service).count()
        )
        change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.SOURCE
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(DeploymentChange.ChangeType.UPDATE, change.type)
        self.assertEqual(None, change.old_value)
        self.assertEqual(
            {
                "username": "fredkiss3",
                "password": "s3cret",
            },
            change.new_value["credentials"],
        )

    def test_create_service_returns_changes_in_response(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "kiss-cam"},
        )
        p = Project.objects.get(slug="kiss-cam")

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertIsNotNone(data)

        self.assertTrue("unapplied_changes" in data)

    def test_request_simple_field_changes(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
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

        self.assertEqual(
            1, DeploymentChange.objects.filter(service__slug=service.slug).count()
        )
        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug=service.slug,
            field=DeploymentChange.ChangeField.SOURCE,
        ).first()
        self.assertEqual({"image": "ghcr.io/zane-ops/app"}, change.new_value)

    def test_request_compound_changes(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": "volumes",
            "type": "ADD",
            "new_value": {
                "name": "zane-logs",
                "container_path": "/etc/logs/zane",
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

        change: DeploymentChange = DeploymentChange.objects.filter(
            Q(service__slug=service.slug) & Q(field="volumes")
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(DeploymentChange.ChangeType.ADD, change.type)

    def test_validate_credentials_with_image(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
                "credentials": {
                    "username": "fredkiss3",
                    "password": "bad",
                },
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
        self.assertEqual(1, DeploymentChange.objects.count())

    def test_add_resource_limits_changes(self):
        p, service = self.create_redis_docker_service()

        resource_limits = {
            "cpus": 1.5,
            "memory": {"value": 500, "unit": "MEGABYTES"},
        }
        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": resource_limits,
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
        resource_limit_changes: DeploymentChange = DeploymentChange.objects.filter(
            field=DeploymentChange.ChangeField.RESOURCE_LIMITS,
            service__slug=service.slug,
        ).first()
        self.assertIsNotNone(resource_limit_changes)
        self.assertEqual(
            resource_limits,
            resource_limit_changes.new_value,
        )

    def test_validate_resource_limits_empty_is_considered_as_null(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {},
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
        changes: DeploymentChange = DeploymentChange.objects.filter(
            field=DeploymentChange.ChangeField.RESOURCE_LIMITS,
            service__slug=service.slug,
        ).first()
        self.assertIsNone(changes)

    def test_validate_credentials_empty_is_considered_as_null(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
                "credentials": {
                    "username": "",
                    "password": "",
                },
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
        changes: DeploymentChange = DeploymentChange.objects.filter(
            field=DeploymentChange.ChangeField.SOURCE,
            service__slug=service.slug,
        ).first()
        self.assertIsNone(changes.new_value.get("credentials"))

    def test_validate_credentials_cannot_pass_username_without_password(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
                "credentials": {
                    "username": "helloworld",
                    "password": "",
                },
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

    def test_validate_credentials_cannot_pass_password_without_username(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
                "credentials": {
                    "username": "",
                    "password": "supersecret123",
                },
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

    def test_validate_credentials_empty_object_is_considered_as_null(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
                "credentials": {},
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
        changes: DeploymentChange = DeploymentChange.objects.filter(
            field=DeploymentChange.ChangeField.SOURCE,
            service__slug=service.slug,
        ).first()
        self.assertIsNone(changes.new_value.get("credentials"))

    def test_validate_resource_limits_cannot_use_less_than_6mb(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "memory": {"value": 5, "unit": "MEGABYTES"},
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

    def test_validate_resource_limits_cannot_go_over_host_cpu_limits(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "cpus": self.fake_docker_client.HOST_CPUS + 1,
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

    def test_validate_resource_limits_cannot_go_over_host_memory_limits(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "memory": {
                    "value": self.fake_docker_client.HOST_MEMORY_IN_BYTES + 1,
                    "unit": "BYTES",
                },
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

    def test_validate_volume_cannot_specify_the_same_container_path_twice_with_pending_changes(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.create(
            field="volumes",
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "mode": "READ_WRITE",
                "name": "zane-logs",
                "container_path": "/etc/logs/zane",
            },
            service=service,
        )

        changes_payload = {
            "field": "volumes",
            "type": "ADD",
            "new_value": {
                "name": "zane-logs2",
                "container_path": "/etc/logs/zane",
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

    def test_validate_volume_cannot_specify_the_same_container_path_twice_with_existing_volumes(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        volume = Volume.objects.create(
            name="zane-logs", container_path="/etc/logs/zane"
        )
        service.volumes.add(volume)

        changes_payload = {
            "field": "volumes",
            "type": "ADD",
            "new_value": {
                "name": "zane-logs2",
                "container_path": "/etc/logs/zane",
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

    def test_validate_conflicting_changes_with_previous_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")
        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zaneops/app",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug="app")
        v = Volume.objects.create(container_path="/etc/logs", name="zane-logs")
        service.volumes.add(v)

        DeploymentChange.objects.create(
            field="volumes",
            type=DeploymentChange.ChangeType.UPDATE,
            item_id=v.id,
            new_value={
                "mode": "READ_ONLY",
                "name": "zane-logs",
                "container_path": "/etc/logs/zane",
            },
            service=service,
        )

        changes_payload = {
            "field": "volumes",
            "type": "DELETE",
            "item_id": v.id,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_cannot_specify_the_same_host_path_twice(self):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.create(
            field=DeploymentChange.ChangeField.VOLUMES,
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "mode": Volume.VolumeMode.READ_ONLY,
                "name": "zane-logs",
                "container_path": "/etc/localtime",
                "host_path": "/etc/localtime",
            },
            service=service,
        )

        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": "ADD",
            "new_value": {
                "name": "zane-logs2",
                "container_path": "/etc/logs/zane",
                "host_path": "/etc/localtime",
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

    def test_validate_volume_host_volume_defaults_to_readonly(self):
        self.loginUser()
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "name": "docker socket",
                "container_path": "/var/run/docker.sock",
                "host_path": "/var/run/docker.sock",
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
        change: DeploymentChange = DeploymentChange.objects.filter(
            service=service, field=DeploymentChange.ChangeField.VOLUMES
        ).first()
        self.assertEqual(Volume.VolumeMode.READ_ONLY, change.new_value.get("mode"))

    def test_validate_volume_allow_host_volume_only_on_readonly(self):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "mode": Volume.VolumeMode.READ_WRITE,
                "name": "docker socket",
                "container_path": "/var/run/docker.sock",
                "host_path": "/var/run/docker.sock",
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

    def test_validate_volume_cannot_use_the_same_host_path_as_another_service(self):
        p, service = self.create_redis_docker_service()
        v = Volume.objects.create(
            host_path="/etc/localtime", container_path="/etc/locatime"
        )

        changes_payload = {
            "field": "volumes",
            "type": "ADD",
            "new_value": {
                "name": "zane-localtime",
                "container_path": "/etc/logs/zane",
                "host_path": "/etc/localtime",
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

    def test_validate_volume_can_use_the_same_host_path_as_another_service_if_both_read_only(
        self,
    ):
        p, service = self.create_redis_docker_service()
        Volume.objects.create(
            host_path="/etc/localtime",
            container_path="/etc/locatime",
            mode=Volume.VolumeMode.READ_ONLY,
        )

        changes_payload = {
            "field": "volumes",
            "type": "ADD",
            "new_value": {
                "name": "zane-localtime",
                "container_path": "/etc/logs/zane",
                "host_path": "/etc/localtime",
                "mode": Volume.VolumeMode.READ_ONLY,
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

    def test_validate_volume_can_use_the_same_host_path_if_same_service(self):
        p, service = self.create_redis_docker_service()
        v = Volume.objects.create(
            host_path="/etc/localtime", container_path="/etc/locatime"
        )
        service.volumes.add(v)

        changes_payload = {
            "field": "volumes",
            "type": "UPDATE",
            "item_id": v.id,
            "new_value": {
                "name": "zane-localtime",
                "container_path": "/etc/logs/zane",
                "host_path": "/etc/localtime",
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

    def test_validate_volume_cannot_delete_host_path_if_existing(self):
        p, service = self.create_redis_docker_service()
        v = Volume.objects.create(
            host_path="/etc/localtime", container_path="/etc/locatime"
        )
        service.volumes.add(v)

        changes_payload = {
            "field": "volumes",
            "type": "UPDATE",
            "item_id": v.id,
            "new_value": {
                "name": "zane-localtime",
                "container_path": "/etc/logs/zane",
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

    def test_validate_volume_cannot_add_host_path_if_not_existing(self):
        p, service = self.create_redis_docker_service()
        v = Volume.objects.create(container_path="/etc/locatime")
        service.volumes.add(v)

        changes_payload = {
            "field": "volumes",
            "type": "UPDATE",
            "item_id": v.id,
            "new_value": {
                "name": "zane-localtime",
                "container_path": "/etc/logs/zane",
                "host_path": "/etc/logs/zane",
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

    def test_validate_env_cannot_specify_the_same_key_twice(self):
        p, service = self.create_redis_docker_service()
        DeploymentChange.objects.create(
            field="env_variables",
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "key": "SECRET_KEY",
                "value": "super5EC4TK4YYY",
            },
            service=service,
        )

        changes_payload = {
            "field": "env_variables",
            "type": "ADD",
            "new_value": {
                "key": "SECRET_KEY",
                "value": "superS3c4t",
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

    def test_validate_ports_cannot_specify_the_same_host_port_twice(self):
        p, service = self.create_redis_docker_service()
        DeploymentChange.objects.create(
            field="ports",
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "host": 8888,
                "forwarded": 3000,
            },
            service=service,
        )

        changes_payload = {
            "field": "ports",
            "type": "ADD",
            "new_value": {
                "host": 8888,
                "forwarded": 8000,
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

    def test_validate_ports_cannot_use_unavailable_host_port(self):
        p, service = self.create_caddy_docker_service()

        changes_payload = {
            "field": "ports",
            "type": "ADD",
            "new_value": {
                "host": self.fake_docker_client.PORT_USED_BY_HOST,
                "forwarded": 80,
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

    def test_validate_ports_cannot_use_port_already_used_by_other_services(self):
        p, redis = self.create_redis_docker_service()
        redis.ports.add(
            PortConfiguration.objects.create(
                host=8082,
                forwarded=5540,
            )
        )

        service = Service.objects.create(
            slug="app",
            project=p,
            image="caddy:2.8-alpine",
            environment=p.production_env,
        )

        changes_payload = {
            "field": "ports",
            "type": "ADD",
            "new_value": {
                "host": 8082,
                "forwarded": 80,
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

    def test_validate_ports_can_update_port_if_in_the_same_service(self):
        p, service = self.create_redis_docker_service()
        port = PortConfiguration.objects.create(
            host=8082,
            forwarded=5540,
        )

        service.ports.add(port)

        changes_payload = {
            "field": "ports",
            "type": "UPDATE",
            "item_id": port.id,
            "new_value": {
                "host": 8082,
                "forwarded": 80,
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

    def test_validate_ports_can_delete_even_if_healthcheck_path_in_service(
        self,
    ):
        p, service = self.create_redis_docker_service()
        port = PortConfiguration.objects.create(forwarded=80, host=8080)
        service.ports.add(port)
        DeploymentChange.objects.create(
            field="healthcheck",
            type=DeploymentChange.ChangeType.UPDATE,
            new_value={
                "type": "PATH",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
            service=service,
        )

        changes_payload = {
            "field": "ports",
            "type": "DELETE",
            "item_id": port.id,
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

    def test_validate_url_cannot_specify_the_same_url_twice(self):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field="urls",
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "dcr.fredkiss.dev",
                        "base_path": "/portainer",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field="ports",
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 9000},
                    service=service,
                ),
            ]
        )

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
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

    def test_validate_url_cannot_use_zane_domain(self):
        p, service = self.create_caddy_docker_service()

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": settings.ZANE_APP_DOMAIN},
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

    def test_validate_url_cannot_use_subdomain_if_wildcard_exists_and_is_used_by_another_service(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        redis = Service.objects.create(
            slug="cache-db", image="redis", project=p, environment=p.production_env
        )
        redis.urls.add(URL.objects.create(domain="*.gh.fredkiss.dev"))

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": "abc.gh.fredkiss.dev"},
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

    def test_validate_url_cannot_use_zane_domain_as_wildcard(self):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.create(
            field="ports",
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "host": 80,
                "forwarded": 3000,
            },
            service=service,
        )

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": f"*.{settings.ZANE_APP_DOMAIN}"},
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

    def test_validate_url_cannot_use_root_domain_as_wildcard(self):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.create(
            field="ports",
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "host": 80,
                "forwarded": 3000,
            },
            service=service,
        )

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": f"*.{settings.ROOT_DOMAIN}"},
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

    def test_validate_url_cannot_specify_custom_url_and_public_port_at_the_same_time(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.create(
            field="ports",
            type=DeploymentChange.ChangeType.ADD,
            new_value={
                "host": 5430,
                "forwarded": 3000,
            },
            service=service,
        )

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": "labs.idx.co"},
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

    def test_validate_url_can_update_url_if_attached_to_same_service(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        url = URL.objects.create(domain="labs.idx.co")
        service.urls.add(url)

        changes_payload = {
            "field": "urls",
            "type": "UPDATE",
            "item_id": url.id,
            "new_value": {
                "domain": "labs.idx.co",
                "associated_port": 8000,
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

    def test_validate_url_cannot_update_url_if_not_attached_to_same_service(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        url = URL.objects.create(domain="labs.idx.co")
        service2 = Service.objects.create(
            slug="other-app", project=p, environment=p.production_env
        )
        service2.urls.add(url)

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "item_id": url.id,
            "new_value": {"domain": "labs.idx.co"},
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

    def test_validate_healthcheck_path_require_associated_port(
        self,
    ):
        p, service = self.create_caddy_docker_service()

        changes_payload = {
            "field": "healthcheck",
            "type": "UPDATE",
            "new_value": {
                "type": "PATH",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
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

    def test_validate_healthcheck_cmd_do_not_require_associated_port(
        self,
    ):
        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": "healthcheck",
            "type": "UPDATE",
            "new_value": {
                "type": "COMMAND",
                "value": "redis-cli PING",
                "timeout_seconds": 30,
                "interval_seconds": 5,
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

    def test_cannot_add_changes_on_nonexistant_projet(self):
        p, service = self.create_caddy_docker_service()

        changes_payload = {
            "field": "image",
            "type": "UPDATE",
            "new_value": "ghcr.io/zane-ops/app",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": "project",
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_cannot_add_changes_on_nonexistant_service(self):
        p, service = self.create_caddy_docker_service()

        changes_payload = {
            "field": "image",
            "type": "UPDATE",
            "new_value": "ghcr.io/zane-ops/app",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DockerServiceDeploymentCancelChangesViewTests(AuthAPITestCase):
    def test_cancel_simple_changes(self):
        p, service = self.create_caddy_docker_service()

        change = DeploymentChange.objects.create(
            field=DeploymentChange.ChangeField.COMMAND,
            type=DeploymentChange.ChangeType.UPDATE,
            new_value="echo 1",
            service=service,
        )

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
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        change_count = DeploymentChange.objects.filter(
            service=service, applied=False
        ).count()
        self.assertEqual(1, change_count)

    def test_cannot_cancel_nonexistent_changes(self):
        p, service = self.create_caddy_docker_service()

        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": "val_123",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_cannot_cancel_a_change_that_sets_image_null(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )

        p = Project.objects.get(slug="zaneops")
        create_service_payload = {"slug": "caddy", "image": "caddy:2.8-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = Service.objects.get(slug="caddy")

        change = service.unapplied_changes.first()

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


class DockerServiceDeploymentApplyChangesViewTests(AuthAPITestCase):
    def test_apply_simple_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {"slug": "caddy", "image": "caddy:2.8-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )

        service = Service.objects.get(slug="caddy")
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
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual("caddy:2.8-alpine", updated_service.image)
        self.assertEqual(0, updated_service.unapplied_changes.count())
        self.assertEqual(1, updated_service.applied_changes.count())

    def test_deploy_service_with_commit_message(self):
        p, service = self.create_caddy_docker_service()

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data={"commit_message": "Initial deployment"},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = response.json()
        self.assertEqual("Initial deployment", new_deployment.get("commit_message"))

    def test_apply_resource_limits(self):
        p, service = self.create_caddy_docker_service()

        resource_limits = {
            "cpus": 1.5,
            "memory": {"value": 500, "unit": "MEGABYTES"},
        }
        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value=resource_limits,
                    service=service,
                ),
            ]
        )

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
        service.refresh_from_db()
        self.assertEqual(resource_limits, service.resource_limits)

    def test_deploy_service_with_blank_commit_message_uses_default_message(self):
        p, service = self.create_caddy_docker_service()

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data={"commit_message": ""},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = response.json()
        self.assertEqual("update service", new_deployment.get("commit_message"))

    def test_deploy_service_without_commit_message_create_default_message(self):
        p, service = self.create_caddy_docker_service()

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
        new_deployment = response.json()
        self.assertEqual("update service", new_deployment.get("commit_message"))

    def test_apply_volume_changes(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        volume_to_delete, volume_to_update = Volume.objects.bulk_create(
            [
                Volume(
                    container_path="/etc/localtime",
                    host_path="/etc/localtime",
                    name="to delete",
                ),
                Volume(container_path="/other", name="to update"),
            ]
        )
        service.volumes.add(volume_to_delete, volume_to_update)

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=volume_to_update.id,
                    new_value={
                        "host_path": "/etc/config",
                        "container_path": "/config",
                        "name": "caddy config",
                        "mode": Volume.VolumeMode.READ_ONLY,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=volume_to_delete.id,
                    service=service,
                ),
            ]
        )

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
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual(2, updated_service.volumes.count())

        new_volume = updated_service.volumes.filter(container_path="/data").first()
        self.assertIsNotNone(new_volume)
        self.assertGreater(len(new_volume.name), 0)

        deleted_volume = updated_service.volumes.filter(id=volume_to_delete.id).first()
        self.assertIsNone(deleted_volume)

        updated_volume = updated_service.volumes.get(id=volume_to_update.id)
        self.assertEqual(Volume.VolumeMode.READ_ONLY, updated_volume.mode)
        self.assertEqual("/etc/config", updated_volume.host_path)
        self.assertEqual("/config", updated_volume.container_path)
        self.assertEqual("caddy config", updated_volume.name)

    def test_apply_env_changes(self):
        p, service = self.create_caddy_docker_service()
        env_to_delete, env_to_update = EnvVariable.objects.bulk_create(
            [
                EnvVariable(
                    key="TO_DELETE", value="random bullshit", service_id=service.id
                ),
                EnvVariable(key="TO_UPDATE", value="old value", service_id=service.id),
            ]
        )

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "DJANGO_SECRET_KEY",
                        "value": "super-secret-key-value-random123",
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=env_to_update.id,
                    new_value={
                        "key": "ENVIRONMENT",
                        "value": "production",
                    },
                    service=service,
                ),
                DeploymentChange(
                    field="env_variables",
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=env_to_delete.id,
                    service=service,
                ),
            ]
        )

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
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual(2, updated_service.env_variables.count())

        new_env = updated_service.env_variables.filter(key="DJANGO_SECRET_KEY").first()
        self.assertIsNotNone(new_env)

        deleted_env = updated_service.env_variables.filter(id=env_to_delete.id).first()
        self.assertIsNone(deleted_env)

        updated_env = updated_service.env_variables.get(id=env_to_update.id)
        self.assertEqual("ENVIRONMENT", updated_env.key)
        self.assertEqual("production", updated_env.value)

    def test_apply_healthcheck_changes_creates_healthcheck_if_not_exists(self):
        p, service = self.create_caddy_docker_service()
        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "caddy validate",
                    },
                    service=service,
                ),
            ]
        )

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
        updated_service = Service.objects.get(slug=service.slug)
        self.assertIsNotNone(updated_service.healthcheck)

    def test_apply_healthcheck_changes_updates_healthcheck_if_exists(self):
        p, service = self.create_caddy_docker_service()
        service.healthcheck = HealthCheck.objects.create(type="COMMAND", value="/")
        service.save()
        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field="healthcheck",
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/status",
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
            ]
        )

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
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual("PATH", updated_service.healthcheck.type)
        self.assertEqual("/status", updated_service.healthcheck.value)
        self.assertEqual(30, updated_service.healthcheck.timeout_seconds)
        self.assertEqual(5, updated_service.healthcheck.interval_seconds)

    def test_apply_changes_creates_a_deployment(self):
        p, service = self.create_caddy_docker_service()

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
        updated_service = Service.objects.get(slug=service.slug)
        new_deployment: Deployment = updated_service.deployments.first()
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.service_snapshot)
        for new_change in updated_service.applied_changes:
            self.assertIsNotNone(new_change.deployment)
            self.assertEqual(new_change.deployment.id, new_deployment.id)


class DockerServiceDeploymentUpdateViewTests(AuthAPITestCase):
    async def test_update_service_set_different_deployment_slot(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment = await service.deployments.order_by("queued_at").afirst()
        second_deployment = await service.deployments.order_by("queued_at").alast()
        self.assertNotEqual(first_deployment.slot, second_deployment.slot)
        self.assertEqual(Deployment.DeploymentSlot.BLUE, first_deployment.slot)
        self.assertEqual(Deployment.DeploymentSlot.GREEN, second_deployment.slot)

    async def test_update_service_set_old_deployment_as_non_production(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment = await service.deployments.order_by("queued_at").afirst()
        second_deployment = await service.deployments.order_by("queued_at").alast()
        self.assertFalse(first_deployment.is_current_production)
        self.assertTrue(second_deployment.is_current_production)

    async def test_update_service_scale_down_and_remove_old_deployment(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "Spec": {
                        "ContainerSpec": {"Image": "ghcr.io/zane-ops/zane-ops:v1.11.1"}
                    },
                    "DesiredState": "running",
                }
            ],  # first deployment
            [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "Spec": {
                        "ContainerSpec": {"Image": "ghcr.io/zane-ops/zane-ops:v1.11.1"}
                    },
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: Deployment = (
            await service.deployments.filter()
            .select_related("service")
            .order_by("queued_at")
            .afirst()
        )
        self.assertEqual(Deployment.DeploymentStatus.REMOVED, first_deployment.status)
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.scale.assert_called_with(0)
        fake_service.remove.assert_called()

    async def test_update_service_with_volume_remove_deleted_volume(self):
        project, service = await self.acreate_and_deploy_redis_docker_service(
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
        volume_to_delete: Volume = await service.volumes.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.DELETE,
                    service=service,
                    item_id=volume_to_delete.id,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        self.assertEqual(0, len(self.fake_docker_client.volume_map))

    async def test_update_service_schedule_next_queued_deployment_on_finish(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        third_deployment: Deployment = await Deployment.objects.acreate(service=service)
        third_deployment.service_snapshot = await sync_to_async(
            lambda: ServiceSerializer(service).data
        )()
        await third_deployment.asave()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())
        second_deployment = await (
            Deployment.objects.filter().select_related("service").afirst()
        )
        self.assertEqual(Deployment.DeploymentStatus.REMOVED, second_deployment.status)
        self.assertIsNone(
            self.fake_docker_client.get_deployment_service(second_deployment)
        )

        third_deployment = await (
            Deployment.objects.filter(hash=third_deployment.hash)
            .select_related("service")
            .afirst()
        )
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, third_deployment.status)
        self.assertIsNotNone(
            self.fake_docker_client.get_deployment_service(third_deployment)
        )

    async def test_update_service_schedule_next_queued_deployment_even_if_fails(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        third_deployment = await Deployment.objects.acreate(service=service)
        third_deployment.service_snapshot = await sync_to_async(
            lambda: ServiceSerializer(service).data
        )()
        await third_deployment.asave()
        print(f"{third_deployment.hash=}")

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )

        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [
                0,
                31,  # -> second deployment will fail healthcheck
                0,
                15,
                30,
                30,  # -> third deployment will succeed healthcheck
            ]
            response = await self.async_client.put(
                reverse(
                    "zane_api:services.docker.deploy_service",
                    kwargs={
                        "project_slug": project.slug,
                        "env_slug": "production",
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        second_deployment = await (
            Deployment.objects.filter().select_related("service").afirst()
        )
        self.assertEqual(Deployment.DeploymentStatus.FAILED, second_deployment.status)

        third_deployment = await (
            Deployment.objects.filter(hash=third_deployment.hash)
            .select_related("service")
            .afirst()
        )
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, third_deployment.status)
        self.assertIsNotNone(
            self.fake_docker_client.get_deployment_service(third_deployment)
        )

    async def test_update_service_do_not_set_different_deployment_slot_if_first_deployment_fails(
        self,
    ):
        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            project, service = await self.acreate_and_deploy_redis_docker_service()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment = await service.deployments.order_by("queued_at").afirst()
        second_deployment = await service.deployments.order_by("queued_at").alast()
        self.assertEqual(first_deployment.slot, second_deployment.slot)

    async def test_remove_new_service_if_deployment_fails(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )

        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            response = await self.async_client.put(
                reverse(
                    "zane_api:services.docker.deploy_service",
                    kwargs={
                        "project_slug": project.slug,
                        "env_slug": "production",
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .afirst()
        )
        second_deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .alast()
        )

        old_docker_service = self.fake_docker_client.get_deployment_service(
            first_deployment
        )
        new_docker_service = self.fake_docker_client.get_deployment_service(
            second_deployment
        )
        self.assertIsNone(new_docker_service)
        self.assertIsNotNone(old_docker_service)

    async def test_scale_back_if_new_deployment_fails(
        self,
    ):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 6379, "host": 6380},
                    service=service,
                ),
            ]
        )

        with patch("temporal.activities.main_activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            fake_service = MagicMock()
            fake_service.tasks.side_effect = lambda *args, **kwargs: []
            fake_service_list = MagicMock()
            fake_service_list.get.return_value = fake_service
            self.fake_docker_client.services = fake_service_list

            response = await self.async_client.put(
                reverse(
                    "zane_api:services.docker.deploy_service",
                    kwargs={
                        "project_slug": project.slug,
                        "env_slug": "production",
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: Deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .afirst()
        )
        self.assertEqual(Deployment.DeploymentStatus.STARTING, first_deployment.status)
        fake_service_list.get.assert_has_calls(
            [
                call(
                    get_swarm_service_name_for_deployment(
                        deployment_hash=first_deployment.hash,
                        service_id=first_deployment.service_id,
                        project_id=first_deployment.service.project_id,
                    )
                )
            ],
            any_order=True,
        )
        fake_service.update.assert_called()
        scaled_up = any(
            call.kwargs.get("mode") == {"Replicated": {"Replicas": 1}}
            for call in fake_service.update.call_args_list
        )
        self.assertTrue(scaled_up)

    async def test_update_url_delete_old_url_from_caddy(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service()

        old_url: URL = await service.urls.afirst()

        await DeploymentChange.objects.acreate(
            field=DeploymentChange.ChangeField.URLS,
            type=DeploymentChange.ChangeType.UPDATE,
            item_id=old_url.id,
            new_value={
                "domain": "proxy.fredkiss.dev",
                "base_path": "/config",
                "strip_prefix": False,
                "id": old_url.id,
            },
            old_value=dict(
                domain=old_url.domain,
                base_path=old_url.base_path,
                strip_prefix=old_url.strip_prefix,
                id=old_url.id,
            ),
            service=service,
        )

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

        new_url: URL = await service.urls.afirst()

        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(service.id, new_url)
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(service.id, old_url)
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_update_url_do_not_delete_old_url_if_still_used(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/",
                        "strip_prefix": False,
                        "associated_port": 80,
                    },
                )
            ]
        )

        old_url: URL = await service.urls.filter(domain="proxy.fredkiss.dev").afirst()

        await DeploymentChange.objects.acreate(
            field=DeploymentChange.ChangeField.URLS,
            type=DeploymentChange.ChangeType.UPDATE,
            item_id=old_url.id,
            new_value={
                "domain": "proxy.fredkiss.dev",
                "base_path": "/",
                "strip_prefix": True,
                "associated_port": 80,
            },
            old_value=dict(
                domain=old_url.domain,
                base_path=old_url.base_path,
                strip_prefix=old_url.strip_prefix,
                id=old_url.id,
            ),
            service=service,
        )

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

        new_url: URL = await service.urls.afirst()

        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(service.id, new_url)
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.get(
            ZaneProxyClient.get_uri_for_service_url(service.id, old_url)
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    async def test_dont_do_zero_downtime_when_updating_with_volumes(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],
            [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "Spec": {
                        "ContainerSpec": {"Image": "ghcr.io/zane-ops/zane-ops:v1.11.1"}
                    },
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"container_path": "/data", "mode": "READ_WRITE"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: Deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .afirst()
        )
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.update.assert_called()
        scaled_down = any(
            call.kwargs.get("mode") == {"Replicated": {"Replicas": 0}}
            for call in fake_service.update.call_args_list
        )
        self.assertTrue(scaled_down)

    async def test_do_zero_downtime_when_updating_with_only_read_only_volumes(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],
            [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "Spec": {
                        "ContainerSpec": {"Image": "ghcr.io/zane-ops/zane-ops:v1.11.1"}
                    },
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/var/run/docker.sock",
                        "mode": "READ_ONLY",
                        "host_path": "/var/run/docker.sock",
                    },
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: Deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .afirst()
        )
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.update.assert_not_called()
        scaled_down = any(
            call.kwargs.get("mode") == {"Replicated": {"Replicas": 0}}
            for call in fake_service.update.call_args_list
        )
        self.assertFalse(scaled_down)

    async def test_dont_do_zero_downtime_when_updating_with_host_ports(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],
            [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "Spec": {
                        "ContainerSpec": {"Image": "ghcr.io/zane-ops/zane-ops:v1.11.1"}
                    },
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 6379, "host": 6380},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: Deployment = await (
            service.deployments.order_by("queued_at").select_related("service").afirst()
        )
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.update.assert_called()
        scaled_down = any(
            call.kwargs.get("mode") == {"Replicated": {"Replicas": 0}}
            for call in fake_service.update.call_args_list
        )
        self.assertTrue(scaled_down)

    async def test_update_service_remove_previous_monitor_task(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .afirst()
        )
        second_deployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .alast()
        )
        self.assertIsNone(
            self.get_workflow_schedule_by_id(first_deployment.monitor_schedule_id)
        )
        self.assertIsNotNone(
            self.get_workflow_schedule_by_id(second_deployment.monitor_schedule_id)
        )


class DockerServiceRedeploymentViewTests(AuthAPITestCase):
    async def test_redeploy_create_deployment_with_computed_changes(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: Deployment = await service.deployments.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Redeploy
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        last_deployment: Deployment = await (
            service.deployments.order_by("queued_at")
            .select_related("is_redeploy_of")
            .alast()
        )
        self.assertIsNotNone(last_deployment.service_snapshot)
        self.assertEqual(initial_deployment, last_deployment.is_redeploy_of)
        self.assertEqual(1, await last_deployment.changes.acount())

        change: DeploymentChange = await last_deployment.changes.afirst()
        self.assertEqual(DeploymentChange.ChangeType.UPDATE, change.type)
        self.assertEqual(DeploymentChange.ChangeField.SOURCE, change.field)
        self.assertEqual("valkey/valkey:7.2-alpine", change.new_value.get("image"))
        self.assertEqual("valkey/valkey:7.3-alpine", change.old_value.get("image"))

        await service.arefresh_from_db()
        self.assertEqual("valkey/valkey:7.2-alpine", service.image)

    async def test_redeploy_save_creates_service_in_docker(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: Deployment = await service.deployments.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Redeploy
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        last_deployment: Deployment = await service.deployments.order_by(
            "queued_at"
        ).alast()
        self.assertTrue(last_deployment.is_current_production)
        docker_service = self.fake_docker_client.get_deployment_service(last_deployment)
        self.assertIsNotNone(docker_service)

    async def test_redeploy_create_set_different_slot(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: Deployment = await service.deployments.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "valkey/valkey:7.3-alpine"},
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        second_deployment: Deployment = await service.deployments.order_by(
            "queued_at"
        ).alast()

        # We Redeploy twice to set the slot to `GREEN`, because `BLUE` is the default value
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": second_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment: Deployment = await service.deployments.order_by(
            "queued_at"
        ).alast()
        self.assertIsNotNone(latest_deployment.service_snapshot)
        self.assertEqual(Deployment.DeploymentSlot.GREEN, latest_deployment.slot)

    async def test_redeploy_complex_service(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            with_healthcheck=False,
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
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "caddy-demo.zaneops.local",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 80,
                    },
                ),
            ],
        )

        initial_deployment: Deployment = await service.deployments.afirst()
        url_to_update: URL = await service.urls.filter(
            domain="caddy-demo.zaneops.local"
        ).afirst()
        volume_to_delete: Volume = await service.volumes.filter(
            container_path="/data"
        ).afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=url_to_update.id,
                    new_value={
                        "domain": "caddy-one.zaneops.local",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 80,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value=None,
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=volume_to_delete.id,
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "CADDY_ADMIN",
                        "value": "0.0.0.0:2019",
                    },
                    service=service,
                ),
            ]
        )

        # deploy changes
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Redeploy
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        await service.arefresh_from_db()

        self.assertEqual(3, await service.deployments.acount())

        self.assertEqual(2, await service.urls.acount())
        url: URL | None = await service.urls.filter(
            domain="caddy-demo.zaneops.local"
        ).afirst()
        self.assertIsNotNone(url)

        url: URL | None = await service.urls.filter(
            domain="caddy-one.zaneops.local"
        ).afirst()
        self.assertIsNone(url)

        self.assertEqual(1, await service.volumes.acount())
        self.assertEqual(0, await service.env_variables.acount())
