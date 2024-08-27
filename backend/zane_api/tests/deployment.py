from unittest.mock import patch, Mock, MagicMock, call

import requests
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import (
    Project,
    DockerDeployment,
    DockerRegistryService,
    DockerDeploymentChange,
    Volume,
    PortConfiguration,
    URL,
    HealthCheck,
    DockerEnvVariable,
)
from ..serializers import DockerServiceSerializer
from ..temporal import (
    get_swarm_service_name_for_deployment,
    get_caddy_uri_for_url,
)
from ..utils import jprint, convert_value_to_bytes


class DockerServiceDeploymentViewTests(AuthAPITestCase):
    def test_get_deployments_succesful(self):
        project, service = self.create_and_deploy_redis_docker_service()
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": project.slug,
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
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": project.slug,
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
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": "inexistent",
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
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_get_single_deployment_succesful(self):
        project, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_single",
                kwargs={
                    "project_slug": project.slug,
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
                "zane_api:services.docker.deployment_single",
                kwargs={
                    "project_slug": project.slug,
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
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": project.slug,
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
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(created_service)
        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service=created_service
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual("image", change.field)
        self.assertEqual(DockerDeploymentChange.ChangeType.UPDATE, change.type)
        self.assertEqual(None, change.old_value)
        self.assertEqual("redis:alpine", change.new_value)

    def test_create_service_with_custom_registry_creates_credential_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(
            2, DockerDeploymentChange.objects.filter(service=created_service).count()
        )
        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service=created_service, field="credentials"
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(DockerDeploymentChange.ChangeType.UPDATE, change.type)
        self.assertEqual(None, change.old_value)
        self.assertEqual(
            {
                "username": "fredkiss3",
                "password": "s3cret",
            },
            change.new_value,
        )

    def test_create_service_returns_changes_in_response(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertIsNotNone(data)

        self.assertTrue("unapplied_changes" in data)

    def test_request_simple_field_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zaneops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": "image",
            "type": "UPDATE",
            "new_value": "ghcr.io/zane-ops/app",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app", field="image"
        ).first()
        self.assertEqual("ghcr.io/zane-ops/app", change.new_value)

    def test_request_compound_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zane-ops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            Q(service__slug="app") & Q(field="volumes")
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(DockerDeploymentChange.ChangeType.ADD, change.type)

    def test_validate_credentials_with_previous_image(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zane-ops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": "credentials",
            "type": "UPDATE",
            "new_value": {
                "username": "fredkiss3",
                "password": "bad",
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(1, DockerDeploymentChange.objects.count())

    def test_add_resource_limits_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zane-ops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "cpus": 1.5,
                "memory": {"value": 500, "unit": "MEGABYTES"},
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        resource_limit_changes: DockerDeploymentChange = (
            DockerDeploymentChange.objects.filter(
                field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
                service__slug="app",
            ).first()
        )
        self.assertIsNotNone(resource_limit_changes)
        self.assertEqual(
            {
                "cpus": 1.5,
                "memory": {"value": 500, "unit": "MEGABYTES"},
            },
            resource_limit_changes.new_value,
        )

    def test_validate_resource_limits_cannot_use_less_than_6mb(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zane-ops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "memory": {"value": 5, "unit": "MEGABYTES"},
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_resource_limits_cannot_go_over_host_limits(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zane-ops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "cpus": self.fake_docker_client.HOST_CPUS + 1,
                "memory": {
                    "value": self.fake_docker_client.HOST_MEMORY_IN_BYTES + 1,
                    "unit": "BYTES",
                },
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_new_image_with_existing_credentials(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zane-ops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = DockerRegistryService.objects.get(slug="app")
        DockerDeploymentChange.objects.create(
            field="credentials",
            new_value={
                "username": "fredkiss3",
                "password": "s3cret",
            },
            service=service,
        )

        changes_payload = {
            "field": "image",
            "type": "UPDATE",
            "new_value": self.fake_docker_client.NONEXISTANT_PRIVATE_IMAGE,
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_cannot_specify_the_same_container_path_twice_with_pending_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field="volumes",
            type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_cannot_specify_the_same_container_path_twice_with_existing_volumes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_conflicting_changes_with_previous_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "ghcr.io/zaneops/app",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = DockerRegistryService.objects.get(slug="app")
        v = Volume.objects.create(container_path="/etc/logs", name="zane-logs")
        service.volumes.add(v)

        DockerDeploymentChange.objects.create(
            field="volumes",
            type=DockerDeploymentChange.ChangeType.UPDATE,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_cannot_specify_the_same_host_path_twice(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field=DockerDeploymentChange.ChangeField.VOLUMES,
            type=DockerDeploymentChange.ChangeType.ADD,
            new_value={
                "mode": Volume.VolumeMode.READ_ONLY,
                "name": "zane-logs",
                "container_path": "/etc/localtime",
                "host_path": "/etc/localtime",
            },
            service=service,
        )

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.VOLUMES,
            "type": "ADD",
            "new_value": {
                "name": "zane-logs2",
                "container_path": "/etc/logs/zane",
                "host_path": "/etc/localtime",
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_host_volume_defaults_to_readonly(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.VOLUMES,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "name": "docker socket",
                "container_path": "/var/run/docker.sock",
                "host_path": "/var/run/docker.sock",
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service=service, field=DockerDeploymentChange.ChangeField.VOLUMES
        ).first()
        self.assertEqual(Volume.VolumeMode.READ_ONLY, change.new_value.get("mode"))

    def test_validate_volume_allow_host_volume_only_on_readonly(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.VOLUMES,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "mode": Volume.VolumeMode.READ_WRITE,
                "name": "docker socket",
                "container_path": "/var/run/docker.sock",
                "host_path": "/var/run/docker.sock",
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_cannot_use_the_same_host_path_as_another_service(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_can_use_the_same_host_path_as_another_service_if_both_read_only(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        DockerRegistryService.objects.create(slug="app", project=p)
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_volume_can_use_the_same_host_path_if_same_service(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_volume_cannot_delete_host_path_if_existing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_volume_cannot_add_host_path_if_not_existing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_env_cannot_specify_the_same_key_twice(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field="env_variables",
            type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_cannot_specify_the_same_host_port_twice(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field="ports",
            type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_cannot_use_unavailable_host_port(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(
            slug="app", project=p, image="caddy:2.8-alpine"
        )

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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_cannot_use_port_already_used_by_other_services(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        redis = DockerRegistryService.objects.create(
            slug="cache-db", image="redis", project=p
        )
        redis.ports.add(
            PortConfiguration.objects.create(
                host=8082,
                forwarded=5540,
            )
        )

        service = DockerRegistryService.objects.create(
            slug="app", project=p, image="caddy:2.8-alpine"
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_can_update_port_if_in_the_same_service(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        port = PortConfiguration.objects.create(
            host=8082,
            forwarded=5540,
        )

        service = DockerRegistryService.objects.create(
            slug="app", project=p, image="caddy:2.8-alpine"
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_ports_cannot_specify_two_http_ports(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(
            slug="app", project=p, image="caddy:2.8-alpine"
        )
        DockerDeploymentChange.objects.create(
            field="ports",
            type=DockerDeploymentChange.ChangeType.ADD,
            new_value={
                "host": 443,
                "forwarded": 3000,
            },
            service=service,
        )

        changes_payload = {
            "field": "ports",
            "type": "ADD",
            "new_value": {
                "host": 80,
                "forwarded": 80,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_cannot_delete_if_healthcheck_path_in_service(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        port = PortConfiguration.objects.create(forwarded=80)
        service.ports.add(port)
        DockerDeploymentChange.objects.create(
            field="healthcheck",
            type=DockerDeploymentChange.ChangeType.UPDATE,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_can_delete_if_healthcheck_path_in_service_and_url_exists(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        port = PortConfiguration.objects.create(forwarded=80)
        service.ports.add(port)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="urls",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "labs.idx.co",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
            ]
        )

        changes_payload = {
            "field": "ports",
            "type": "DELETE",
            "item_id": port.id,
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_cannot_specify_the_same_url_twice(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="urls",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "dcr.fredkiss.dev",
                        "base_path": "/portainer",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="ports",
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_cannot_use_zane_domain(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": settings.ZANE_APP_DOMAIN},
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_cannot_use_subdomain_if_wildcard_exists(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        redis = DockerRegistryService.objects.create(
            slug="cache-db", image="redis", project=p
        )
        redis.urls.add(URL.objects.create(domain="*.gh.fredkiss.dev"))

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": "abc.gh.fredkiss.dev"},
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_cannot_use_zane_domain_as_wildcard(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field="ports",
            type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_cannot_use_root_domain_as_wildcard(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field="ports",
            type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_cannot_specify_custom_url_and_public_port_at_the_same_time(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.create(
            field="ports",
            type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_require_forwarded_http_port(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": "labs.idx.co"},
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_cannot_delete_if_healthcheck_path_in_service(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url = URL.objects.create(domain="labs.idx.co")
        service.urls.add(url)
        DockerDeploymentChange.objects.create(
            field="healthcheck",
            type=DockerDeploymentChange.ChangeType.UPDATE,
            new_value={
                "type": "PATH",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
            service=service,
        )

        changes_payload = {
            "field": "urls",
            "type": "DELETE",
            "item_id": url.id,
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_can_delete_if_healthcheck_path_in_service_and_port_exists(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url = URL.objects.create(domain="labs.idx.co")
        service.urls.add(url)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="ports",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "forwarded": 80,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
            ]
        )

        changes_payload = {
            "field": "urls",
            "type": "DELETE",
            "item_id": url.id,
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_can_update_url_if_attached_to_same_service(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url = URL.objects.create(domain="labs.idx.co")
        service.urls.add(url)

        changes_payload = {
            "field": "urls",
            "type": "UPDATE",
            "item_id": url.id,
            "new_value": {"domain": "labs.idx.co"},
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_cannot_update_url_if_not_attached_to_same_service(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url = URL.objects.create(domain="labs.idx.co")
        service2 = DockerRegistryService.objects.create(slug="other-app", project=p)
        service2.urls.add(url)

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "item_id": url.id,
            "new_value": {"domain": "labs.idx.co"},
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_ports_cannot_specify_custom_url_and_public_port_at_the_same_time(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="urls",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "labs.idx.co",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="ports",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 9000},
                    service=service,
                ),
            ]
        )

        changes_payload = {
            "field": "ports",
            "type": "ADD",
            "new_value": {
                "host": 5430,
                "forwarded": 3000,
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_healthcheck_path_require_url_or_http_port(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        DockerRegistryService.objects.create(slug="app", project=p)

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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_healthcheck_cmd_do_not_require_url_or_http_port(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        DockerRegistryService.objects.create(
            slug="app", project=p, image="redis:alpine"
        )

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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_healthcheck_path_works_with_http_port(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="ports",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 9000},
                    service=service,
                ),
            ]
        )

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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_healthcheck_path_works_with_url(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="urls",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "labs.idx.co",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
            ]
        )

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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_cannot_add_changes_on_nonexistant_projet(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": "image",
            "type": "UPDATE",
            "new_value": "ghcr.io/zane-ops/app",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": "project", "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_cannot_add_changes_on_nonexistant_service(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        changes_payload = {
            "field": "image",
            "type": "UPDATE",
            "new_value": "ghcr.io/zane-ops/app",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DockerServiceDeploymentCancelChangesViewTests(AuthAPITestCase):
    def test_cancel_simple_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes = DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="credentials",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"username": "fredkiss3", "password": "s3c4et"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": changes[0].id,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        change_count = DockerDeploymentChange.objects.filter(
            service=service, applied=False
        ).count()
        self.assertEqual(1, change_count)

    def test_cannot_cancel_nonexistent_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        DockerRegistryService.objects.create(slug="app", project=p)

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": "val_123",
                },
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_cannot_cancel_a_change_that_sets_image_null(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        change = DockerDeploymentChange.objects.create(
            field="image",
            type=DockerDeploymentChange.ChangeType.UPDATE,
            new_value="caddy:2.8-alpine",
            service=service,
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_cancel_port_change_if_healthcheck_path(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        port_change, _, _ = DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="ports",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": port_change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_cancel_url_change_if_healthcheck_path(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url_change, _, _ = DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="urls",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "portainer.com",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 5,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        changes_payload = {
            "change_id": url_change.id,
        }
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": url_change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_can_cancel_port_change_if_no_healthcheck_path_in_service(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        port_change, _ = DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="ports",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": port_change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

    def test_can_cancel_url_change_if_no_healthcheck_path_in_service(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url_change, _ = DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="urls",
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "portainer.com",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                    "change_id": url_change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)


class DockerServiceDeploymentApplyChangesViewTests(AuthAPITestCase):
    def test_apply_simple_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CREDENTIALS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "username": "fredkiss3",
                        "password": "5ec43t",
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual("caddy:2.8-alpine", updated_service.image)
        self.assertEqual(
            {
                "username": "fredkiss3",
                "password": "5ec43t",
            },
            updated_service.credentials,
        )
        self.assertEqual(0, updated_service.unapplied_changes.count())
        self.assertEqual(2, updated_service.applied_changes.count())

    def test_deploy_service_with_commit_message(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
            data={"commit_message": "Initial deployment"},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = response.json()
        self.assertEqual("Initial deployment", new_deployment.get("commit_message"))

    def test_apply_resource_limits(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        resource_limits = {
            "cpus": 1.5,
            "memory": {"value": 500, "unit": "MEGABYTES"},
        }
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        self.assertEqual(resource_limits, service.resource_limits)

    def test_deploy_service_with_blank_commit_message_uses_default_message(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
            data={"commit_message": ""},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = response.json()
        self.assertEqual("update service", new_deployment.get("commit_message"))

    def test_deploy_service_without_commit_message_create_default_message(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = response.json()
        self.assertEqual("update service", new_deployment.get("commit_message"))

    def test_apply_volume_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=volume_to_update.id,
                    new_value={
                        "host_path": "/etc/config",
                        "container_path": "/config",
                        "name": "caddy config",
                        "mode": Volume.VolumeMode.READ_ONLY,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
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

    def test_apply_env_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        env_to_delete, env_to_update = DockerEnvVariable.objects.bulk_create(
            [
                DockerEnvVariable(
                    key="TO_DELETE", value="random bullshit", service_id=service.id
                ),
                DockerEnvVariable(
                    key="TO_UPDATE", value="old value", service_id=service.id
                ),
            ]
        )

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "DJANGO_SECRET_KEY",
                        "value": "super-secret-key-value-random123",
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=env_to_update.id,
                    new_value={
                        "key": "ENVIRONMENT",
                        "value": "production",
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field="env_variables",
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual(2, updated_service.env_variables.count())

        new_env = updated_service.env_variables.filter(key="DJANGO_SECRET_KEY").first()
        self.assertIsNotNone(new_env)

        deleted_env = updated_service.env_variables.filter(id=env_to_delete.id).first()
        self.assertIsNone(deleted_env)

        updated_env = updated_service.env_variables.get(id=env_to_update.id)
        self.assertEqual("ENVIRONMENT", updated_env.key)
        self.assertEqual("production", updated_env.value)

    def test_apply_url_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        url_to_delete, url_to_update = URL.objects.bulk_create(
            [
                URL(base_path="/unused", domain="old-domain.com"),
                URL(base_path="/", domain="caddy-test.fredkiss.dev"),
            ]
        )
        service.urls.add(url_to_delete, url_to_update)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=url_to_update.id,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/config",
                        "strip_prefix": False,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.DELETE,
                    item_id=url_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual(2, updated_service.urls.count())

        new_url = updated_service.urls.filter(domain="web-server.fred.kiss").first()
        self.assertIsNotNone(new_url)

        deleted_url = updated_service.urls.filter(id=url_to_delete.id).first()
        self.assertIsNone(deleted_url)

        updated_url = updated_service.urls.get(id=url_to_update.id)
        self.assertEqual("proxy.fredkiss.dev", updated_url.domain)
        self.assertEqual("/config", updated_url.base_path)
        self.assertEqual(False, updated_url.strip_prefix)

    def test_apply_port_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        port_to_delete, port_to_update = PortConfiguration.objects.bulk_create(
            [
                PortConfiguration(host=1010, forwarded=1010),
                PortConfiguration(forwarded=8000, host=8000),
            ]
        )
        service.ports.add(port_to_delete, port_to_update)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "forwarded": 9000,
                        "host": 9000,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=port_to_update.id,
                    new_value={
                        "forwarded": 80,
                        "host": 8080,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.DELETE,
                    item_id=port_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual(2, updated_service.ports.count())

        new_port = updated_service.ports.filter(host=9000).first()
        self.assertIsNotNone(new_port)

        deleted_port = updated_service.ports.filter(id=port_to_delete.id).first()
        self.assertIsNone(deleted_port)

        updated_port = updated_service.ports.get(id=port_to_update.id)
        self.assertEqual(8080, updated_port.host)
        self.assertEqual(80, updated_port.forwarded)

    def test_apply_http_port_changes_without_url_creates_default_url(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")

        new_port = updated_service.ports.filter(host__isnull=True).first()
        self.assertIsNotNone(new_port)
        self.assertEqual(80, new_port.forwarded)
        self.assertEqual(1, updated_service.urls.count())

    def test_apply_http_port_changes_with_url_do_not_create_default_url(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "labs.zane.co",
                        "base_path": "/app",
                        "strip_prefix": False,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual(1, updated_service.urls.count())
        service_url: URL = updated_service.urls.first()
        self.assertEqual("labs.zane.co", service_url.domain)
        self.assertEqual("/app", service_url.base_path)
        self.assertEqual(False, service_url.strip_prefix)

    def test_apply_healthcheck_changes_creates_healthcheck_if_not_exists(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertIsNotNone(updated_service.healthcheck)

    def test_apply_healthcheck_changes_updates_healthcheck_if_exists(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        service.healthcheck = HealthCheck.objects.create(type="COMMAND", value="/")
        service.save()
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field="image",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field="healthcheck",
                    type=DockerDeploymentChange.ChangeType.UPDATE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual("PATH", updated_service.healthcheck.type)
        self.assertEqual("/status", updated_service.healthcheck.value)
        self.assertEqual(30, updated_service.healthcheck.timeout_seconds)
        self.assertEqual(5, updated_service.healthcheck.interval_seconds)

    def test_apply_changes_creates_a_deployment(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(
            slug="basic-web-server", project=p
        )
        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="ghcr.io/caddy:2.8-alpine-with-python",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CREDENTIALS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"username": "fredkiss3", "password": "s3cret"},
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "basic-web-server",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="basic-web-server")
        new_deployment: DockerDeployment = updated_service.deployments.first()
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.service_snapshot)
        for new_change in updated_service.applied_changes:
            self.assertIsNotNone(new_change.deployment)
            self.assertEqual(new_change.deployment.id, new_deployment.id)

    def test_apply_changes_creates_a_deployment_with_url_if_service_has_url_provided(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="caddy:2.8-alpine",
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 80, "host": 80},
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        new_deployment: DockerDeployment = updated_service.deployments.first()
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.url)


class DockerServiceDeploymentCreateResourceTests(AuthAPITestCase):
    async def test_deploy_simple_service(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY, new_deployment.status
        )
        self.assertTrue(new_deployment.is_current_production)

    async def test_deploy_service_with_env(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "REDIS_PASSWORD",
                        "value": "super-secret-key-value-random123",
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertTrue("REDIS_PASSWORD" in docker_service.env)

    async def test_deploy_service_with_volumes(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)

        self.assertIsNotNone(docker_service)
        self.assertEqual(1, len(self.fake_docker_client.volume_map))
        self.assertEqual(1, len(docker_service.attached_volumes))

        new_volume = await service.volumes.afirst()
        self.assertIsNotNone(docker_service.get_attached_volume(new_volume))

    async def test_deploy_service_with_resource_limits(self):
        await self.aLoginUser()
        resource_limits = {
            "cpus": 1.5,
            "memory": {"value": 500, "unit": "MEGABYTES"},
        }
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value=resource_limits,
                ),
            ]
        )
        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        self.assertIsNotNone(docker_service.resources)

        nano_cpus = resource_limits.get("cpus") * 1e9
        memory_bytes = convert_value_to_bytes(
            value=resource_limits.get("memory")["value"],
            unit=resource_limits.get("memory")["unit"],
        )
        self.assertEqual(
            nano_cpus, docker_service.resources.get("Limits").get("NanoCPUs")
        )
        self.assertEqual(
            memory_bytes, docker_service.resources.get("Limits").get("MemoryBytes")
        )

    async def test_deploy_service_with_volumes_do_not_create_resources_for_volumes_with_host_path(
        self,
    ):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "host_path": "/var/www/caddy/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

        self.assertEqual(0, len(self.fake_docker_client.volume_map))
        self.assertEqual(1, len(docker_service.attached_volumes))

    async def test_deploy_service_with_volumes_do_not_include_deleted_volumes(
        self,
    ):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/delete",
                        "host_path": "/delete",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
            ]
        )
        volume_to_delete = await service.volumes.filter(host_path="/delete").afirst()
        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.DELETE,
                    item_id=volume_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)

        self.assertIsNotNone(docker_service)
        self.assertEqual(1, len(docker_service.attached_volumes))
        self.assertIsNone(docker_service.get_attached_volume(volume_to_delete))

    async def test_deploy_service_with_port(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"host": 6383, "forwarded": 6379},
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)

        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)
        self.assertIsNotNone(docker_service.endpoint)

        port_in_docker = docker_service.endpoint.get("Ports")[0]
        self.assertEqual(6383, port_in_docker["PublishedPort"])
        self.assertEqual(6379, port_in_docker["TargetPort"])

    async def test_deploy_service_with_http_port(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service()

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNone(docker_service.endpoint)

    async def test_deploy_service_with_http_port_exposes_the_service(
        self,
    ):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service()

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        service_url: URL = await service.urls.afirst()
        response = requests.get(get_caddy_uri_for_url(service_url))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    async def test_deploy_service_with_urls(
        self,
    ):
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        service_url: URL = await service.urls.filter(
            domain="web-server.fred.kiss"
        ).afirst()
        response = requests.get(get_caddy_uri_for_url(service_url))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    async def test_deploy_service_set_started_at(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service()
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.started_at)

    async def test_deploy_service_set_finished_at_on_success(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service()
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertIsNotNone(new_deployment.finished_at)

    @patch("zane_api.temporal.activities.monotonic")
    async def test_deploy_service_set_finished_at_on_fail(
        self,
        mock_monotonic: Mock,
    ):
        mock_monotonic.side_effect = [0, 31]
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        new_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertIsNotNone(new_deployment.finished_at)

    @patch("zane_api.temporal.activities.monotonic")
    async def test_deploy_service_set_deployment_failed_when_healthcheck_fails(
        self,
        mock_monotonic: Mock,
    ):
        mock_monotonic.side_effect = [0, 31]
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        new_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED, new_deployment.status
        )

    @patch("zane_api.temporal.activities.monotonic")
    async def test_deploy_service_set_deployment_to_production_when_healthcheck_fails_if_unique(
        self,
        mock_monotonic: Mock,
    ):
        mock_monotonic.side_effect = [0, 31]
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        new_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED, new_deployment.status
        )
        self.assertTrue(new_deployment.is_current_production)

    async def test_deploy_service_do_not_set_deployment_to_production_when_healthcheck_fails(
        self,
    ):
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 30]
            response = await self.async_client.put(
                reverse(
                    "zane_api:services.docker.deploy_service",
                    kwargs={
                        "project_slug": p.slug,
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED, new_deployment.status
        )
        self.assertFalse(new_deployment.is_current_production)


class DockerServiceDeploymentUpdateViewTests(AuthAPITestCase):
    async def test_update_service_set_different_deployment_slot(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment = await service.deployments.order_by("queued_at").afirst()
        second_deployment = await service.deployments.order_by("queued_at").alast()
        self.assertNotEqual(first_deployment.slot, second_deployment.slot)
        self.assertEqual(DockerDeployment.DeploymentSlot.BLUE, first_deployment.slot)
        self.assertEqual(DockerDeployment.DeploymentSlot.GREEN, second_deployment.slot)

    async def test_update_service_set_old_deployment_as_non_production(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
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
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: DockerDeployment = (
            await service.deployments.filter()
            .select_related("service")
            .order_by("queued_at")
            .afirst()
        )
        self.assertEqual(
            DockerDeployment.DeploymentStatus.REMOVED, first_deployment.status
        )
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
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                )
            ]
        )
        volume_to_delete: Volume = await service.volumes.afirst()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        self.assertEqual(0, len(self.fake_docker_client.volume_map))

    async def test_update_service_schedule_next_queued_deployment_on_finish(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        third_deployment: DockerDeployment = await DockerDeployment.objects.acreate(
            service=service
        )
        third_deployment.service_snapshot = await sync_to_async(
            lambda: DockerServiceSerializer(service).data
        )()
        await third_deployment.asave()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())
        second_deployment = await (
            DockerDeployment.objects.filter().select_related("service").afirst()
        )
        self.assertEqual(
            DockerDeployment.DeploymentStatus.REMOVED, second_deployment.status
        )
        self.assertIsNone(
            self.fake_docker_client.get_deployment_service(second_deployment)
        )

        third_deployment = await (
            DockerDeployment.objects.filter(hash=third_deployment.hash)
            .select_related("service")
            .afirst()
        )
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY, third_deployment.status
        )
        self.assertIsNotNone(
            self.fake_docker_client.get_deployment_service(third_deployment)
        )

    async def test_update_service_schedule_next_queued_deployment_even_if_fails(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        third_deployment = await DockerDeployment.objects.acreate(service=service)
        third_deployment.service_snapshot = await sync_to_async(
            lambda: DockerServiceSerializer(service).data
        )()
        await third_deployment.asave()
        print(f"{third_deployment.hash=}")

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )

        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
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
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        second_deployment = await (
            DockerDeployment.objects.filter().select_related("service").afirst()
        )
        self.assertEqual(
            DockerDeployment.DeploymentStatus.FAILED, second_deployment.status
        )
        # self.assertIsNone(
        #     self.fake_docker_client.get_deployment_service(second_deployment)
        # )

        third_deployment = await (
            DockerDeployment.objects.filter(hash=third_deployment.hash)
            .select_related("service")
            .afirst()
        )
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY, third_deployment.status
        )
        self.assertIsNotNone(
            self.fake_docker_client.get_deployment_service(third_deployment)
        )

    async def test_update_service_do_not_set_different_deployment_slot_if_first_deployment_fails(
        self,
    ):
        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            project, service = await self.acreate_and_deploy_redis_docker_service()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
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

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )

        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            response = await self.async_client.put(
                reverse(
                    "zane_api:services.docker.deploy_service",
                    kwargs={
                        "project_slug": project.slug,
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

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"forwarded": 6379, "host": 6380},
                    service=service,
                ),
            ]
        )

        with patch("zane_api.temporal.activities.monotonic") as mock_monotonic:
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
                        "service_slug": service.slug,
                    },
                ),
            )
            self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: DockerDeployment = (
            await service.deployments.order_by("queued_at")
            .select_related("service")
            .afirst()
        )
        self.assertEqual(
            DockerDeployment.DeploymentStatus.STARTING, first_deployment.status
        )
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
        fake_service.scale.assert_has_calls(
            [call(1)],
            any_order=True,
        )

    async def test_update_url_delete_old_url_from_caddy(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service()

        old_url: URL = await service.urls.afirst()

        await DockerDeploymentChange.objects.acreate(
            field=DockerDeploymentChange.ChangeField.URLS,
            type=DockerDeploymentChange.ChangeType.UPDATE,
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
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_url: URL = await service.urls.afirst()

        response = requests.get(get_caddy_uri_for_url(new_url))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.get(get_caddy_uri_for_url(old_url))
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_update_url_do_not_delete_old_url_if_still_used(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/",
                        "strip_prefix": False,
                    },
                )
            ]
        )

        old_url: URL = await service.urls.afirst()

        await DockerDeploymentChange.objects.acreate(
            field=DockerDeploymentChange.ChangeField.URLS,
            type=DockerDeploymentChange.ChangeType.UPDATE,
            item_id=old_url.id,
            new_value={
                "domain": "proxy.fredkiss.dev",
                "base_path": "/",
                "strip_prefix": True,
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
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_url: URL = await service.urls.afirst()

        response = requests.get(get_caddy_uri_for_url(new_url))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.get(get_caddy_uri_for_url(old_url))
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
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: DockerDeployment = (
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
        self.assertEqual(2, fake_service.scale.call_count)
        fake_service.scale.assert_called_with(0)

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
                    "DesiredState": "running",
                }
            ],  # first deployment
            [],  # second deployment
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        first_deployment: DockerDeployment = await (
            service.deployments.order_by("queued_at").select_related("service").afirst()
        )
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        self.assertEqual(2, fake_service.scale.call_count)
        fake_service.scale.assert_called_with(0)

    async def test_update_service_remove_previous_monitor_task(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
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
        initial_deployment: DockerDeployment = await service.deployments.afirst()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
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
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        last_deployment: DockerDeployment = await (
            service.deployments.order_by("queued_at")
            .select_related("is_redeploy_of")
            .alast()
        )
        self.assertIsNotNone(last_deployment.service_snapshot)
        self.assertEqual(initial_deployment, last_deployment.is_redeploy_of)
        self.assertEqual(1, await last_deployment.changes.acount())

        change: DockerDeploymentChange = await last_deployment.changes.afirst()
        self.assertEqual(DockerDeploymentChange.ChangeType.UPDATE, change.type)
        self.assertEqual(DockerDeploymentChange.ChangeField.IMAGE, change.field)
        self.assertEqual("valkey/valkey:7.2-alpine", change.new_value)
        self.assertEqual("valkey/valkey:7.3-alpine", change.old_value)

        await service.arefresh_from_db()
        self.assertEqual("valkey/valkey:7.2-alpine", service.image)

    async def test_redeploy_save_creates_service_in_docker(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: DockerDeployment = await service.deployments.afirst()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
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
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        last_deployment: DockerDeployment = await service.deployments.order_by(
            "queued_at"
        ).alast()
        self.assertTrue(last_deployment.is_current_production)
        docker_service = self.fake_docker_client.get_deployment_service(last_deployment)
        self.assertIsNotNone(docker_service)

    async def test_redeploy_create_set_different_slot(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()
        initial_deployment: DockerDeployment = await service.deployments.afirst()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.IMAGE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="valkey/valkey:7.3-alpine",
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        second_deployment: DockerDeployment = await service.deployments.order_by(
            "queued_at"
        ).alast()

        # We Redeploy twice to set the slot to `GREEN`, because `BLUE` is the default value
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
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
                    "service_slug": service.slug,
                    "deployment_hash": second_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        latest_deployment: DockerDeployment = await service.deployments.order_by(
            "queued_at"
        ).alast()
        self.assertIsNotNone(latest_deployment.service_snapshot)
        self.assertEqual(DockerDeployment.DeploymentSlot.GREEN, latest_deployment.slot)

    async def test_redeploy_complex_service(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            with_healthcheck=False,
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "caddy-demo.zaneops.local",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                ),
            ],
        )

        initial_deployment: DockerDeployment = await service.deployments.afirst()
        url_to_update: URL = await service.urls.filter(
            domain="caddy-demo.zaneops.local"
        ).afirst()
        volume_to_delete: Volume = await service.volumes.filter(
            container_path="/data"
        ).afirst()

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=url_to_update.id,
                    new_value={
                        "domain": "caddy-one.zaneops.local",
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value=None,
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.DELETE,
                    item_id=volume_to_delete.id,
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        await service.arefresh_from_db()

        self.assertEqual(3, await service.deployments.acount())

        self.assertEqual(1, await service.urls.acount())
        url: URL = await service.urls.afirst()
        self.assertEqual("caddy-demo.zaneops.local", url.domain)

        self.assertEqual(1, await service.volumes.acount())
        self.assertEqual(0, await service.env_variables.acount())


class DockerToggleServiceViewTests(AuthAPITestCase):
    async def test_stop_service(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        first_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertIsNotNone(first_deployment)
        self.assertEqual(
            DockerDeployment.DeploymentStatus.SLEEPING, first_deployment.status
        )
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.scale.assert_called_with(0)
        monitor_schedule = self.get_workflow_schedule_by_id(
            first_deployment.monitor_schedule_id
        )
        self.assertFalse(monitor_schedule.is_running)

    async def test_restart_service(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        fake_service = MagicMock()
        fake_service.tasks.side_effect = [
            [],  # stopped
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
                    "DesiredState": "running",
                }
            ],  # restarted
        ]
        fake_service_list = MagicMock()
        fake_service_list.get.return_value = fake_service
        self.fake_docker_client.services = fake_service_list

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        first_deployment: DockerDeployment = await service.deployments.afirst()

        self.assertEqual(
            DockerDeployment.DeploymentStatus.STARTING, first_deployment.status
        )
        fake_service_list.get.assert_called_with(
            get_swarm_service_name_for_deployment(
                deployment_hash=first_deployment.hash,
                service_id=first_deployment.service_id,
                project_id=first_deployment.service.project_id,
            )
        )
        fake_service.scale.assert_called_with(1)
        monitor_schedule = self.get_workflow_schedule_by_id(
            first_deployment.monitor_schedule_id
        )
        self.assertTrue(monitor_schedule.is_running)

    async def test_cannot_stop_service_if_not_deployed_yet(self):
        owner = await self.aLoginUser()
        project = await Project.objects.acreate(slug="zaneops", owner=owner)
        service = await DockerRegistryService.objects.acreate(
            slug="app", project=project
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.toggle",
                kwargs={
                    "project_slug": project.slug,
                    "service_slug": service.slug,
                },
            ),
        )

        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
