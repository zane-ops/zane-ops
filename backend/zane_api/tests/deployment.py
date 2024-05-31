from unittest.mock import MagicMock

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
)


class DockerServiceDeploymentViewTests(AuthAPITestCase):
    def test_get_deployments_succesful(self):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))

    def test_create_service_set_deployment_slot(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "valkey",
            "image": "valkey:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="valkey"
        ).first()
        self.assertIsNotNone(created_service)
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(DockerDeployment.DeploymentSlot.BLUE, latest_deployment.slot)

    def test_filter_deployments_succesful(self):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                },
            )
            + "?status=OFFLINE"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(0, len(data))

    def test_deployments_project_non_existing(self):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployments_list",
                kwargs={
                    "project_slug": "inexistent",
                    "service_slug": "cache-db",
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
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_single",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                    "deployment_hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_single_deployment_service_non_existing(self):
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
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_single",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": "cache-db",
                    "deployment_hash": "dkr_dpl_hash1234",
                },
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_add_deployment_url_when_url_is_provided(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "webserver",
            "image": "caddy",
            "urls": [{"domain": "caddy.zaneops.dev"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="webserver"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNotNone(deployment.url)

    def test_add_deployment_url_when_port_is_provided(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "webserver",
            "image": "caddy",
            "ports": [{"forwarded": "80"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="webserver"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNotNone(deployment.url)

    def test_do_not_add_deployment_url_when_no_port_or_url_is_provided(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNone(deployment.url)

    def test_mark_deployment_as_failed_when_the_task_fails(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
        }

        exception = Exception("unexpected exception")

        def create_raise_error(*args, **kwargs):
            raise exception

        self.fake_docker_client.services.create = create_raise_error

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertEqual(DockerDeployment.DeploymentStatus.FAILED, deployment.status)
        self.assertEqual(str(exception), deployment.status_reason)

    def test_scale_down_the_service_for_the_deployment_when_the_task_fails(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis",
            "ports": [{"forwarded": "80"}],
        }

        exception = Exception("unexpected exception")

        def create_raise_error(*args, **kwargs):
            raise exception

        fake_service = MagicMock()
        self.fake_docker_client.services.create = create_raise_error
        self.fake_docker_client.services.list = lambda *args, **kwargs: [fake_service]

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertEqual(DockerDeployment.DeploymentStatus.FAILED, deployment.status)
        self.assertEqual(str(exception), deployment.status_reason)
        fake_service.scale.assert_called_with(0)


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
            field="volumes",
            type=DockerDeploymentChange.ChangeType.ADD,
            new_value={
                "mode": "READ_WRITE",
                "name": "zane-logs",
                "container_path": "/etc/localtime",
                "host_path": "/etc/localtime",
            },
            service=service,
        )

        changes_payload = {
            "field": "volumes",
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

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {"domain": f"*.{settings.ZANE_APP_DOMAIN}"},
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
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
