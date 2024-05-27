from django.urls import reverse
from rest_framework import status

from . import AuthAPITestCase
from ..docker_operations import (
    create_docker_volume,
    get_docker_service_resource_name,
    get_volume_resource_name,
)
from ..models import Project, Volume, DockerRegistryService


class DockerVolumeTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)

    def test_create_volume_successful(self):
        service = DockerRegistryService.objects.create(
            project=Project.objects.get(slug="zane-ops")
        )
        volume = Volume.objects.create(
            name="postgres DB Data",
        )
        create_docker_volume(volume, service)
        self.assertEqual(1, len(self.fake_docker_client.volume_map))

    def test_create_service_with_volume_supports_host_path(self):
        create_service_payload = {
            "slug": "self-github",
            "image": "gitea",
            "volumes": [
                {
                    "name": "Local time",
                    "host_path": "/etc/localtime",
                    "container_path": "/etc/localtime",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="self-github"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume: Volume = created_service.volumes.first()
        self.assertEqual("/etc/localtime", created_volume.host_path)

        self.assertEqual(0, len(self.fake_docker_client.volume_map))

        fake_service = self.fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        self.assertEqual(1, len(fake_service.attached_volumes))

    def test_create_service_with_volume_supports_access_mode(self):
        create_service_payload = {
            "slug": "zane-on-zane",
            "image": "ghcr.io/zane-ops/zane-api",
            "volumes": [
                {
                    "name": "Docker Socket",
                    "container_path": "/var/run/docker.sock",
                    "mode": "READ_ONLY",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="zane-on-zane"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume: Volume = created_service.volumes.first()
        self.assertEqual(Volume.VolumeMode.READ_ONLY, created_volume.mode)

        fake_service = self.fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        fake_volume = fake_service.attached_volumes.get(
            get_volume_resource_name(created_volume)
        )
        self.assertEqual("ro", fake_volume.get("mode"))

    def test_create_service_with_volume_supports_default_access_mode_is_read_write(
        self,
    ):
        create_service_payload = {
            "slug": "zane-on-zane",
            "image": "ghcr.io/zane-ops/zane-api",
            "volumes": [
                {
                    "name": "Docker Socket",
                    "container_path": "/var/run/docker.sock",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="zane-on-zane"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume: Volume = created_service.volumes.first()
        self.assertEqual(Volume.VolumeMode.READ_WRITE, created_volume.mode)

        fake_service = self.fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        fake_volume = fake_service.attached_volumes.get(
            get_volume_resource_name(created_volume)
        )
        self.assertEqual("rw", fake_volume.get("mode"))

    def test_create_service_with_volume_name_is_optional(self):
        create_service_payload = {
            "slug": "self-github",
            "image": "gitea",
            "volumes": [
                {
                    "host_path": "/etc/localtime",
                    "container_path": "/etc/localtime",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="self-github"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume: Volume = created_service.volumes.first()
        self.assertIsNotNone(created_volume.name)

    def test_create_service_with_volume_only_absolute_path_for_host_path(self):
        create_service_payload = {
            "slug": "self-github",
            "image": "gitea",
            "volumes": [
                {
                    "host_path": "./etc/localtime",
                    "container_path": "/etc/localtime",
                }
            ],
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "zane-ops"}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class VolumeGetSizeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)

    def test_get_volume_size(self):
        volume = Volume.objects.create(
            name="postgres DB Data",
        )

        response = self.client.get(
            reverse("zane_api:volume.size", kwargs={"volume_id": volume.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertIsNotNone(data.get("size"))

    def test_non_existant_volume(self):
        response = self.client.get(
            reverse("zane_api:volume.size", kwargs={"volume_id": "abcDefGh1jk"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
