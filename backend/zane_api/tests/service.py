import json
import random
from unittest.mock import patch, Mock

from django.conf import settings
from django.urls import reverse
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from rest_framework import status

from .base import AuthAPITestCase, FakeDockerClient
from ..docker_operations import (
    get_docker_service_resource_name,
    get_volume_resource_name,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    PortConfiguration,
    URL,
    ArchivedDockerService,
    DockerEnvVariable,
    Volume,
    HealthCheck,
)
from ..tasks import monitor_docker_service_deployment


class DockerServiceCreateViewTest(AuthAPITestCase):

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_simple_service(self, mock_fake_docker: Mock, _: Mock):
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
        data = response.json().get("service")
        self.assertIsNotNone(data)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(created_service)
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertTrue(
            get_docker_service_resource_name(
                project_id=p.id, service_id=created_service.id
            )
            in fake_docker_client.service_map
        )

        deployment = DockerDeployment.objects.filter(service=created_service).first()
        self.assertIsNotNone(deployment)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_volume(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "volumes": [{"name": "REDIS Data volume", "mount_path": "/data"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual(1, created_service.volumes.count())

        created_volume = created_service.volumes.first()

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertEqual(1, len(fake_docker_client.volume_map))

        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        self.assertEqual(1, len(fake_service.attached_volumes))
        self.assertIsNotNone(
            fake_service.attached_volumes.get(get_volume_resource_name(created_volume))
        )

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_env_and_command(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "command": "redis-server --requirepass ${REDIS_PASSWORD}",
            "env": {"REDIS_PASSWORD": "strongPassword123"},
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="cache-db"
        ).first()
        env = created_service.env_variables.first()

        self.assertIsNotNone(created_service.command)
        self.assertIsNotNone(env)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]
        self.assertEqual(1, len(fake_service.env))
        self.assertEqual("strongPassword123", fake_service.env.get("REDIS_PASSWORD"))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_port(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "nosql-db",
            "image": "redis:alpine",
            "ports": [{"public": 6383, "forwarded": 6379}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="nosql-db"
        ).first()
        port: PortConfiguration = created_service.ports.first()

        self.assertIsNotNone(port)
        self.assertEqual(6383, port.host)
        self.assertEqual(6379, port.forwarded)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]

        self.assertIsNotNone(fake_service.endpoint)

        port_in_docker = fake_service.endpoint.get("Ports")[0]
        self.assertEqual(6383, port_in_docker["PublishedPort"])
        self.assertEqual(6379, port_in_docker["TargetPort"])

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_should_not_work_with_unavailable_host_port(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "nosql-db",
            "image": "redis:alpine",
            "ports": [
                {"public": FakeDockerClient.PORT_USED_BY_HOST, "forwarded": 6379},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="nosql-db"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_should_not_work_with_port_already_used_by_other_services(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            slug="cache-db", image_repository="redis", project=p
        )

        used_port = PortConfiguration(
            host=8082,
            forwarded=5540,
        )
        used_port.save()
        service.ports.add(used_port)

        create_service_payload = {
            "slug": "adminer",
            "image": "adminer:latest",
            "ports": [{"public": used_port.host, "forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_http_port(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()
        port: PortConfiguration = created_service.ports.first()

        self.assertIsNotNone(port)
        self.assertIsNone(port.host)
        self.assertEqual(8080, port.forwarded)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        fake_service = fake_docker_client.service_map[
            get_docker_service_resource_name(
                service_id=created_service.id,
                project_id=created_service.project.id,
            )
        ]

        self.assertIsNone(fake_service.endpoint)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_port_create_a_default_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()

        default_url: URL = created_service.urls.first()
        self.assertIsNotNone(default_url)
        self.assertEqual(
            f"{p.slug}-{created_service.slug}.{settings.ROOT_DOMAIN}",
            default_url.domain,
        )
        self.assertEqual("/", default_url.base_path)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_default_url_get_regenerated_if_url_already_exists(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        URL.objects.create(domain=f"{p.slug}-adminer-ui.{settings.ROOT_DOMAIN}")

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()

        default_url: URL = created_service.urls.first()
        self.assertIsNotNone(default_url)
        self.assertNotEquals(
            f"{p.slug}-{created_service.slug}.{settings.ROOT_DOMAIN}",
            default_url.domain,
        )
        self.assertEqual("/", default_url.base_path)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_explicit_url(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "portainer-ui",
            "image": "portainer/portainer-ce:latest",
            "urls": [{"domain": "dcr.fredkiss.dev", "base_path": "/portainer"}],
            "ports": [{"forwarded": 8000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="portainer-ui"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("dcr.fredkiss.dev", url.domain)
        self.assertEqual("/portainer", url.base_path)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_wildcard_url_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "gh-next",
            "image": "dcr.fredkiss.dev/gh-next",
            "urls": [{"domain": "*.gh.fredkiss.dev"}],
            "ports": [{"forwarded": 3000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="gh-next"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("*.gh.fredkiss.dev", url.domain)
        self.assertEqual("/", url.base_path)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_can_create_a_service_with_same_parent_domain_even_if_wildcard_exists(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)
        URL.objects.create(domain="*.gh.fredkiss.dev")

        create_service_payload = {
            "slug": "gh-next",
            "image": "dcr.fredkiss.dev/gh-next",
            "urls": [{"domain": "gh.fredkiss.dev"}],
            "ports": [{"forwarded": 3000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="gh-next"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("gh.fredkiss.dev", url.domain)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_cannot_create_a_service_with_same_subdomain_if_wildcard_exists(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)
        URL.objects.create(domain="*.gh.fredkiss.dev")

        create_service_payload = {
            "slug": "gh-next",
            "image": "dcr.fredkiss.dev/gh-next",
            "urls": [{"domain": "abc.gh.fredkiss.dev"}],
            "ports": [{"forwarded": 3000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="gh-next"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_explicit_domain_and_strip_prefix(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "portainer-ui",
            "image": "portainer/portainer-ce:latest",
            "urls": [
                {
                    "domain": "dcr.fredkiss.dev",
                    "base_path": "/portainer",
                    "strip_prefix": False,
                }
            ],
            "ports": [{"forwarded": 8000}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="portainer-ui"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        url: URL = created_service.urls.first()
        self.assertIsNotNone(url)
        self.assertEqual("dcr.fredkiss.dev", url.domain)
        self.assertEqual("/portainer", url.base_path)
        self.assertEqual(False, url.strip_prefix)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_without_port_does_not_create_a_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "main-database",
            "image": "postgres:12-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-database"
        ).first()
        self.assertEqual(0, created_service.urls.count())

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_no_http_public_port_does_not_create_a_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "public-database",
            "image": "postgres:12-alpine",
            "ports": [{"public": 5433, "forwarded": 5432}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="public-database"
        ).first()

        self.assertEqual(0, created_service.urls.count())

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_create_a_domain_if_public_port_is_80_or_443(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [{"public": random.choice([443, 80]), "forwarded": 8080}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()
        self.assertEqual(1, created_service.urls.count())

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_can_only_specify_one_http_port(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [
                {"public": 443, "forwarded": 8080},
                {"public": 80, "forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_cannot_specify_the_same_public_port_twice(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "ports": [
                {"public": 8081, "forwarded": 8080},
                {"public": 8081, "forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_cannot_specify_the_same_url_twice(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "urls": [
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
            ],
            "ports": [
                {"forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_cannot_specify_the_same_volume_mount_path_twice(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "gitea",
            "image": "gitea/gitea:latest",
            "volumes": [
                {"name": "gitea data", "mount_path": "/data"},
                {"name": "gitea config", "mount_path": "/data"},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_cannot_create_service_with_zane_domain(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "urls": [
                {"domain": settings.ZANE_APP_DOMAIN},
            ],
            "ports": [
                {"forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_cannot_specify_custom_url_and_public_port_at_the_same_time(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "portainer-ce:latest",
            "urls": [
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
            ],
            "ports": [
                {"public": 8099, "forwarded": 8080},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_create_implicit_port_if_custom_url_is_specified(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "portainer-ce:latest",
            "urls": [
                {"domain": "dcr.fredkiss.dev", "base_path": "/portainer"},
            ],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="adminer-ui"
        ).first()

        self.assertEqual(1, created_service.urls.count())
        self.assertEqual(1, created_service.ports.count())
        create_port: PortConfiguration = created_service.ports.first()
        self.assertEqual(80, create_port.forwarded)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_custom_registry(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
                "registry_url": "https://dcr.fredkiss.dev/",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNotNone(created_service)
        self.assertEqual("fredkiss3", created_service.docker_credentials_username)
        self.assertEqual("s3cret", created_service.docker_credentials_password)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        self.assertTrue(fake_docker_client.is_logged_in)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_custom_registry_does_not_create_service_if_bad_image_credentials(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/gh-next:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "bad",
                "registry_url": "https://dcr.fredkiss.dev/",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_custom_registry_does_not_create_service_if_nonexistent_image(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()

        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "dcr.fredkiss.dev/nonexistent:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
                "registry_url": "https://dcr.fredkiss.dev/",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        self.assertTrue(fake_docker_client.is_logged_in)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_credentials_do_not_correspond_to_image(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "gcr.io/redis:latest",
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
                "registry_url": "https://dcr.fredkiss.dev/",
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_service_if_nonexistent_dockerhub_image(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        create_service_payload = {
            "slug": "main-app",
            "image": "nonexistent",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_bad_request(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_for_nonexistent_project(
        self, mock_fake_docker: Mock, _: Mock
    ):
        self.loginUser()
        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": "gh-clone"}
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        created_service: DockerRegistryService = DockerRegistryService.objects.filter(
            slug="main-app"
        ).first()
        self.assertIsNone(created_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_conflict_with_slug(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        DockerRegistryService.objects.create(
            slug="cache-db", image_repository="redis", project=p
        )

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_urls_already_used_by_other_services(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        existing_service = DockerRegistryService.objects.create(
            slug="redis", image_repository="redis", project=p
        )
        url = URL.objects.bulk_create(
            [
                URL(domain="thullo.zane.local", base_path="/"),
            ]
        )
        existing_service.urls.add(*url)

        create_service_payload = {
            "slug": "adminer-ui",
            "image": "adminer:latest",
            "urls": [{"domain": "thullo.zane.local"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_slug_is_created_if_not_specified(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = DockerRegistryService.objects.filter().first()
        self.assertIsNotNone(created_service)
        self.assertIsNotNone(created_service.slug)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_slug_is_lowercased(self, mock_fake_docker: Mock, _: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="zane-ops", owner=owner)

        create_service_payload = {
            "slug": "Zane-Ops-fronT",
            "image": "ghcr.io/zane-ops-front:latest",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = DockerRegistryService.objects.filter(
            slug="zane-ops-front"
        ).first()
        self.assertIsNotNone(created_service)


class DockerServicesDeploymentViewTest(AuthAPITestCase):
    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_use_specific_tag_for_deployment_with_the_user_specifed_one(
        self, mock_fake_docker: Mock, _: Mock
    ):
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
        self.assertIsNotNone(deployment)
        self.assertEqual("alpine", deployment.image_tag)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_use_latest_tag_for_deployment_when_no_tag_specifed(
        self, mock_fake_docker: Mock, _: Mock
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
        self.assertEqual("latest", deployment.image_tag)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_add_deployment_url_when_url_is_provided(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "webserver",
            "image": "caddy",
            "urls": [{"domain": "caddy.zaneops.dev"}],
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="webserver"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNotNone(deployment.url)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_add_deployment_url_when_port_is_provided(
        self, mock_fake_docker: Mock, _: Mock
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
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="webserver"
        ).first()
        self.assertIsNotNone(deployment)
        self.assertIsNotNone(deployment.url)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_do_not_add_deployment_url_when_no_port_or_url_is_provided(
        self, mock_fake_docker: Mock, _: Mock
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


class DockerServiceHealthCheckViewTests(AuthAPITestCase):

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_scheduled_task_when_creating_a_service(
        self, mock_fake_docker: Mock, _: Mock
    ):
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
        initial_deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="cache-db"
        ).first()
        self.assertIsNotNone(initial_deployment)
        self.assertIsNotNone(initial_deployment.monitor_task)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_healtheck_creates_healthheck(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "simple-webserver",
            "image": "caddy",
            "ports": [{"forwarded": 80}],
            "healthcheck": {
                "type": "path",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = response.json().get("service")
        self.assertIsNotNone(service.get("healthcheck"))
        created_service = DockerRegistryService.objects.get(slug="simple-webserver")
        self.assertIsNotNone(created_service.healthcheck)
        self.assertEqual("/", created_service.healthcheck.value)
        self.assertEqual(
            HealthCheck.HealthCheckType.PATH, created_service.healthcheck.type
        )
        self.assertEqual(5, created_service.healthcheck.interval_seconds)
        self.assertEqual(30, created_service.healthcheck.timeout_seconds)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_healtheck_cannot_use_invalid_type(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "simple-webserver",
            "image": "caddy:alpine",
            "ports": [{"forwarded": 80}],
            "healthcheck": {
                "type": "invalid",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_healtheck_cannot_use_invalid_path_value(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "simple-webserver",
            "image": "caddy:alpine",
            "ports": [{"forwarded": 80}],
            "healthcheck": {
                "type": "path",
                "value": "dcr.fredkiss.dev/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_healtheck_path_ignore_case(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "simple-webserver",
            "image": "caddy:alpine",
            "ports": [{"forwarded": 80}],
            "healthcheck": {
                "type": "PaTh",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_healtheck_path_require_url_or_port(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "simple-webserver",
            "image": "caddy:alpine",
            "healthcheck": {
                "type": "path",
                "value": "/",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_create_service_with_healtheck_cmd_do_not_require_url_or_port(
        self, mock_fake_docker: Mock, _: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "simple-webserver",
            "image": "redis:alpine",
            "healthcheck": {
                "type": "command",
                "value": "redis-cli PING",
                "timeout_seconds": 30,
                "interval_seconds": 5,
            },
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)


class DockerGetServiceViewTest(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_service_succesful(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        service = DockerRegistryService.objects.create(
            slug="cache-db", image_repository="redis", project=p
        )

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json().get("service")
        self.assertIsNotNone(data)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_service_non_existing(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_service_not_in_the_correct_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p1 = Project.objects.create(slug="kiss-cam", owner=owner)
        p2 = Project.objects.create(slug="camly", owner=owner)

        service = DockerRegistryService.objects.create(
            slug="cache-db", image_repository="redis", project=p1
        )

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={"project_slug": p2.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DockerServiceArchiveViewTest(AuthAPITestCase):
    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_simple_service(self, mock_fake_docker: Mock, _: Mock, __: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service = DockerRegistryService.objects.filter(slug="cache-db").first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = ArchivedDockerService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(archived_service)

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        deleted_docker_service = fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
        self.assertIsNone(deleted_docker_service)

        deployments = DockerDeployment.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deployments))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_service_with_volume(
        self, mock_fake_docker: Mock, _: Mock, __: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "volumes": [{"name": "REDIS Data volume", "mount_path": "/data"}],
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_volumes = Volume.objects.filter(name="REDIS Data volume")
        self.assertEqual(0, len(deleted_volumes))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="cache-db").prefetch_related(
                "volumes"
            )
        ).first()
        self.assertEqual(1, len(archived_service.volumes.all()))

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        deleted_docker_service = fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
        self.assertIsNone(deleted_docker_service)
        self.assertEqual(0, len(fake_docker_client.volume_map))

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_service_with_env_and_command(
        self, mock_fake_docker: Mock, _: Mock, __: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "command": "redis-server --requirepass ${REDIS_PASSWORD}",
            "env": {"REDIS_PASSWORD": "strongPassword123"},
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_envs = DockerEnvVariable.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deleted_envs))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="cache-db").prefetch_related(
                "env_variables"
            )
        ).first()
        self.assertEqual(1, len(archived_service.env_variables.all()))

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        deleted_docker_service = fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
        self.assertIsNone(deleted_docker_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_service_with_port(self, mock_fake_docker: Mock, _: Mock, __: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
            "ports": [{"public": 6383, "forwarded": 6379}],
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_ports = PortConfiguration.objects.filter(host=6383)
        self.assertEqual(0, len(deleted_ports))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="cache-db").prefetch_related(
                "ports"
            )
        ).first()
        self.assertEqual(1, len(archived_service.ports.all()))

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        deleted_docker_service = fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
        self.assertIsNone(deleted_docker_service)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_service_with_urls(self, mock_fake_docker: Mock, _: Mock, __: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="thullo", owner=owner)

        create_service_payload = {
            "slug": "thullo-api",
            "image": "dcr.fredkiss.dev/thullo-api:latest",
            "urls": [{"domain": "thullo.fredkiss.dev", "base_path": "/api"}],
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "thullo-api"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_urls = URL.objects.filter(
            domain="thullo.fredkiss.dev", base_path="/api"
        )
        self.assertEqual(0, len(deleted_urls))

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="thullo-api").prefetch_related(
                "urls"
            )
        ).first()
        self.assertEqual(1, len(archived_service.urls.all()))

        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        deleted_docker_service = fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
        self.assertIsNone(deleted_docker_service)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_service_non_existing(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_service_for_non_existing_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": "zane-ops", "service_slug": "cache-db"},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_should_have_deployment_tag_and_service_image_repository(
        self, mock_fake_docker: Mock, _: Mock, __: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        archived_service: ArchivedDockerService = ArchivedDockerService.objects.filter(
            slug="cache-db"
        ).first()
        self.assertIsNotNone(archived_service)

        self.assertEqual("redis", archived_service.image_repository)
        self.assertEqual("alpine", archived_service.image_tag)

    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_should_delete_monitoring_tasks_for_the_deployment(
        self, mock_fake_docker: Mock, _: Mock, __: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        # create
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )

        # then delete
        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": "cache-db"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deployments = DockerDeployment.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deployments))
        monitoring_tasks = PeriodicTask.objects.all()
        self.assertEqual(0, len(monitoring_tasks))
        schedules = IntervalSchedule.objects.all()
        self.assertEqual(0, len(schedules))


class DockerServiceMonitorTests(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_normal_deployment_flow(self, mock_fake_docker: Mock):
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
        created_service = DockerRegistryService.objects.get(slug="cache-db")
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.PREPARING,
            latest_deployment.deployment_status,
        )
        monitor_docker_service_deployment(latest_deployment.hash)
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.deployment_status,
        )

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_restart_is_set_after_multiple_tasks_deployments(
        self, mock_fake_docker: Mock
    ):
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
        created_service = DockerRegistryService.objects.get(slug="cache-db")
        latest_deployment = created_service.get_latest_deployment()
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        class FakeService:
            @staticmethod
            def tasks(*args, **kwargs):
                return [
                    {
                        "ID": "8qx04v72iovlv7xzjvsj2ngdkg",
                        "Version": {"Index": 15078},
                        "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                        "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:42.770670997Z",
                            "State": "shutdown",
                            "Message": "started",
                            "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ExitCode": 127,
                            },
                        },
                        "DesiredState": "shutdown",
                    },
                    {
                        "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                        "Version": {"Index": 15079},
                        "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                        "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:42.770670997Z",
                            "State": "starting",
                            "Message": "started",
                            # "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ExitCode": 0,
                            },
                        },
                        "DesiredState": "starting",
                    },
                ]

        fake_docker_client.services.get = lambda _id: FakeService()

        self.assertEqual(
            DockerDeployment.DeploymentStatus.PREPARING,
            latest_deployment.deployment_status,
        )
        monitor_docker_service_deployment(latest_deployment.hash)
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.RESTARTING,
            latest_deployment.deployment_status,
        )

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_succesful_restart_deploymen_flow(self, mock_fake_docker: Mock):
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
        created_service = DockerRegistryService.objects.get(slug="cache-db")
        latest_deployment = created_service.get_latest_deployment()
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        class FakeService:
            @staticmethod
            def tasks(*args, **kwargs):
                return [
                    {
                        "ID": "8qx04v72iovlv7xzjvsj2ngdkg",
                        "Version": {"Index": 15078},
                        "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                        "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:42.770670997Z",
                            "State": "shutdown",
                            "Message": "started",
                            "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ExitCode": 127,
                            },
                        },
                        "DesiredState": "shutdown",
                    },
                    {
                        "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                        "Version": {"Index": 15079},
                        "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                        "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:42.770670997Z",
                            "State": "running",
                            "Message": "started",
                            # "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ExitCode": 0,
                            },
                        },
                        "DesiredState": "running",
                    },
                ]

        fake_docker_client.services.get = lambda _id: FakeService()

        self.assertEqual(
            DockerDeployment.DeploymentStatus.PREPARING,
            latest_deployment.deployment_status,
        )
        monitor_docker_service_deployment(latest_deployment.hash)
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.HEALTHY,
            latest_deployment.deployment_status,
        )

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_unsuccesful_restart_deploymen_flow(self, mock_fake_docker: Mock):
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
        created_service = DockerRegistryService.objects.get(slug="cache-db")
        latest_deployment = created_service.get_latest_deployment()
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        class FakeService:
            @staticmethod
            def tasks(*args, **kwargs):
                return [
                    {
                        "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                        "Version": {"Index": 15078},
                        "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                        "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:42.770670997Z",
                            "State": "failed",
                            "Message": "started",
                            "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ContainerID": "a6e983977676b708ed0201c91c4fa3c6fbc4c1d43f7520327db8efc5ba8b76f0",
                                "PID": 0,
                                "ExitCode": 127,
                            },
                            "PortStatus": {},
                        },
                        "DesiredState": "shutdown",
                    },
                    {
                        "ID": "jumpidf77nnc9u24dn2t0t8gk",
                        "Version": {"Index": 15070},
                        "CreatedAt": "2024-04-25T20:11:21.303508844Z",
                        "UpdatedAt": "2024-04-25T20:11:32.93669947Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:32.642315167Z",
                            "State": "failed",
                            "Message": "started",
                            "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ContainerID": "407c4b40d621b127a1cac498d066587522f4ddcca1ec01992dbf94f49c6092fc",
                                "PID": 0,
                                "ExitCode": 127,
                            },
                            "PortStatus": {},
                        },
                        "DesiredState": "shutdown",
                    },
                    {
                        "ID": "wqnwod7cacovpscsp3n6vsgmc",
                        "Version": {"Index": 15091},
                        "CreatedAt": "2024-04-25T20:11:52.686304192Z",
                        "UpdatedAt": "2024-04-25T20:12:02.693438335Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:12:02.415795453Z",
                            "State": "failed",
                            "Message": "started",
                            "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ContainerID": "edd2aa5d80747f860b1cee700a1028e7000970f05a8fe9784fa0f81c460459ac",
                                "PID": 0,
                                "ExitCode": 127,
                            },
                            "PortStatus": {},
                        },
                        "DesiredState": "shutdown",
                    },
                    {
                        "ID": "wwkdns3g7fsyq37hwe5cj7spl",
                        "Version": {"Index": 15086},
                        "CreatedAt": "2024-04-25T20:11:42.863807131Z",
                        "UpdatedAt": "2024-04-25T20:11:52.887691861Z",
                        "Status": {
                            "Timestamp": "2024-04-25T20:11:52.620438735Z",
                            "State": "failed",
                            "Message": "started",
                            "Err": "task: non-zero exit (127)",
                            "ContainerStatus": {
                                "ContainerID": "f45b1785bca08314c9b6af63bdf8080aa79d60a427315d9fe96ba8928d1d1d54",
                                "PID": 0,
                                "ExitCode": 127,
                            },
                            "PortStatus": {},
                        },
                        "DesiredState": "shutdown",
                    },
                ]

        fake_docker_client.services.get = lambda _id: FakeService()

        self.assertEqual(
            DockerDeployment.DeploymentStatus.PREPARING,
            latest_deployment.deployment_status,
        )
        monitor_docker_service_deployment(latest_deployment.hash)
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.UNHEALTHY,
            latest_deployment.deployment_status,
        )

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_service_fail_outside_of_zane_control(self, mock_fake_docker: Mock):
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
        created_service = DockerRegistryService.objects.get(slug="cache-db")
        latest_deployment = created_service.get_latest_deployment()
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value

        class FakeService:
            @staticmethod
            def tasks(*args, **kwargs):
                return []

        fake_docker_client.services.get = lambda _id: FakeService()

        self.assertEqual(
            DockerDeployment.DeploymentStatus.PREPARING,
            latest_deployment.deployment_status,
        )
        latest_deployment.deployment_status = DockerDeployment.DeploymentStatus.HEALTHY
        latest_deployment.save()
        monitor_docker_service_deployment(latest_deployment.hash)
        latest_deployment = created_service.get_latest_deployment()
        self.assertEqual(
            DockerDeployment.DeploymentStatus.UNHEALTHY,
            latest_deployment.deployment_status,
        )


class DockerServiceDeploymentViewTests(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_deployments_succesful(self, mock_fake_docker: Mock):
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

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_filter_deployments_succesful(self, mock_fake_docker: Mock):
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
            + "?deployment_status=HEALTHY"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(0, len(data))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_deployments_project_non_existing(self, mock_fake_docker: Mock):
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

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_deployments_service_non_existing(self, mock_fake_docker: Mock):
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

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_get_single_deployment_succesful(self, mock_fake_docker: Mock):
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

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_single_deployment_service_non_existing(self, mock_fake_docker: Mock):
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
