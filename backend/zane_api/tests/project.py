import datetime
from unittest.mock import patch, Mock

from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase, FakeDockerClient
from ..docker_operations import get_docker_service_resource_name
from ..models import (
    Project,
    ArchivedProject,
    DockerRegistryService,
    ArchivedDockerService,
    DockerDeployment,
    Volume,
    DockerEnvVariable,
    PortConfiguration,
    URL,
)


class ProjectListViewTests(AuthAPITestCase):
    def test_default_no_include_archived(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="thullo"),
            ]
        )

        ArchivedProject.objects.bulk_create(
            [
                ArchivedProject(owner=owner, slug="gh-clone"),
            ]
        )
        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        active_project_list: list = response.json().get("active").get("projects", [])
        archived_project_list = response.json().get("archived").get("projects", [])
        self.assertEqual(1, len(active_project_list))
        self.assertEqual(0, len(archived_project_list))

    def test_list_archived(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="thullo"),
            ]
        )

        ArchivedProject.objects.bulk_create(
            [
                ArchivedProject(owner=owner, slug="gh-clone"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="status=archived",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        active_project_list: list = response.json().get("active").get("projects", [])
        archived_project_list = response.json().get("archived").get("projects", [])
        self.assertEqual(0, len(active_project_list))
        self.assertEqual(1, len(archived_project_list))

    def test_query_filter_active_projects(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="thullo"),
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
            ]
        )
        ArchivedProject.objects.bulk_create(
            [
                ArchivedProject(owner=owner, slug="gh-clone"),
            ]
        )

        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="query=gh",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        active_project_list: list = response.json().get("active").get("projects", [])
        archived_project_list = response.json().get("archived").get("projects", [])
        self.assertEqual(2, len(active_project_list))
        self.assertEqual(0, len(archived_project_list))

    def test_query_filter_archived_projects(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="thullo"),
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
            ]
        )
        ArchivedProject.objects.bulk_create(
            [
                ArchivedProject(owner=owner, slug="gh-clone"),
                ArchivedProject(owner=owner, slug="gh-next"),
                ArchivedProject(owner=owner, slug="zane"),
            ]
        )

        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="query=gh&status=archived",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        active_project_list: list = response.json().get("active").get("projects", [])
        archived_project_list = response.json().get("archived").get("projects", [])
        self.assertEqual(0, len(active_project_list))
        self.assertEqual(2, len(archived_project_list))

    def test_sorting_projects_by_slug(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="thullo"),
                Project(owner=owner, slug="gh-clone"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="sort=slug_asc",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        active_project_list: list = response.json().get("active").get("projects", [])
        self.assertEqual("gh-clone", active_project_list[0]["slug"])

    def test_sorting_projects_by_updated_at(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(
                    owner=owner,
                    slug="thullo",
                    updated_at=datetime.datetime(year=2024, month=3, day=28),
                ),
                Project(
                    owner=owner,
                    slug="gh-clone",
                    updated_at=datetime.datetime(year=2024, month=3, day=29),
                ),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="sort=updated_at_desc",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        active_project_list: list = response.json().get("active").get("projects", [])
        self.assertEqual("gh-clone", active_project_list[0]["slug"])

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)


class ProjectCreateViewTests(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_sucessfully_create_project(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_generate_slug_if_not_specified(self, _: Mock):
        self.loginUser()
        response = self.client.post(reverse("zane_api:projects.list"), data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())
        self.assertIsNotNone(Project.objects.filter().first().slug)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_unique_slug(self, _: Mock):
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, Project.objects.count())

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_invalid_slug(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane Ops"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_slug_is_always_lowercase(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-Ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual("zane-ops", Project.objects.filter().first().slug)


class ProjectUpdateViewTests(AuthAPITestCase):
    def test_sucessfully_update_project_slug(self):
        owner = self.loginUser()
        previous_project = Project.objects.create(slug="gh-next", owner=owner)
        response = self.client.patch(
            reverse(
                "zane_api:projects.details", kwargs={"slug": previous_project.slug}
            ),
            format="json",
            data={
                "slug": "kisshub",
            },
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_project: Project = Project.objects.filter(slug="kisshub").first()
        self.assertIsNotNone(updated_project)
        self.assertEqual("kisshub", updated_project.slug)
        self.assertNotEquals(previous_project.updated_at, updated_project.updated_at)

    def test_bad_request(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", owner=owner),
                Project(slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"slug": "Zane Ops"},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_non_existent(self):
        self.loginUser()
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"name": "zenops"},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_already_existing_slug(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", owner=owner),
                Project(slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"slug": "gh-clone"},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_can_rename_to_self(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", owner=owner),
                Project(slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"slug": "zane-ops"},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class ProjectGetViewTests(AuthAPITestCase):
    def test_sucessfully_get_project(self):
        owner = self.loginUser()
        Project.objects.create(slug="gh-clone", owner=owner),
        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.json().get("project"))

    def test_non_existent(self):
        self.loginUser()
        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class ProjectArchiveViewTests(AuthAPITestCase):
    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_sucessfully_archive_project(self, _: Mock, __: Mock):
        owner = self.loginUser()
        Project.objects.create(slug="gh-clone", owner=owner),
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNone(updated_project)

        archived_project: ArchivedProject = ArchivedProject.objects.filter(
            slug="gh-clone"
        ).first()
        self.assertIsNotNone(archived_project)
        self.assertNotEquals("", archived_project.original_id)

    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_non_existent(self, _: Mock, __: Mock):
        self.loginUser()
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_cannot_archive_already_archived_project(self, _: Mock, __: Mock):
        owner = self.loginUser()
        ArchivedProject.objects.create(slug="zane-ops", owner=owner)
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_can_reuse_archived_version_if_it_exists(self, _: Mock, __: Mock):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)
        ArchivedProject.create_from_project(p)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNone(updated_project)

        archived_projects = ArchivedProject.objects.filter(slug="gh-clone")
        self.assertEqual(1, len(archived_projects))
        self.assertIsNone(archived_projects.first().active_version)

    @patch("zane_api.tasks.unexpose_docker_service_from_http")
    @patch("zane_api.tasks.expose_docker_service_to_http")
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_archive_all_services_when_archiving_a_projects(
        self, mock_fake_docker: Mock, _: Mock, __: Mock
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        create_service_payload = {
            "slug": "gitea",
            "image": "gitea/gitea:latest",
            "urls": [{"domain": "gitea.zane.local", "base_path": "/"}],
            "ports": [{"forwarded": 3000}],
            "env": {"USER_UID": "1000", "USER_GID": "1000"},
            "volumes": [{"name": "gitea", "mount_path": "/data"}],
        }

        # create the service
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
            content_type="application/json",
        )

        # then archive the project
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "sandbox"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Service is deleted
        deleted_service = DockerRegistryService.objects.filter(slug="gitea").first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="gitea")
            .prefetch_related("volumes")
            .prefetch_related("env_variables")
            .prefetch_related("ports")
            .prefetch_related("urls")
        ).first()
        self.assertIsNotNone(archived_service)

        # Deployments are cleaned up
        deployments = DockerDeployment.objects.filter(service__slug="gitea")
        self.assertEqual(0, len(deployments))

        # Volumes are cleaned up
        deleted_volumes = Volume.objects.filter(name="gitea")
        self.assertEqual(0, len(deleted_volumes))
        self.assertEqual(1, len(archived_service.volumes.all()))

        # env variables are cleaned up
        deleted_envs = DockerEnvVariable.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deleted_envs))
        self.assertEqual(2, len(archived_service.env_variables.all()))

        # ports are cleaned up
        deleted_ports = PortConfiguration.objects.filter(host=6383)
        self.assertEqual(0, len(deleted_ports))
        self.assertEqual(1, len(archived_service.ports.all()))

        # urls are cleaned up
        deleted_urls = URL.objects.filter(domain="gitea.zane.local", base_path="/")
        self.assertEqual(0, len(deleted_urls))
        self.assertEqual(1, len(archived_service.urls.all()))

        # --- Docker Resources ---
        # service is removed
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        deleted_docker_service = fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
        self.assertIsNone(deleted_docker_service)

        # volumes are unmounted
        self.assertEqual(0, len(fake_docker_client.volume_map))


class DockerAddNetworkTest(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_network_is_created_on_new_project(self, mock_fake_docker: Mock):
        self.loginUser()
        # Create a new project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        p: Project | None = Project.objects.filter(slug="zane-ops").first()
        self.assertIsNotNone(mock_fake_docker.return_value.get_network(p))


class DockerRemoveNetworkTest(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_network_is_deleted_on_archived_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        p = Project.objects.create(slug="gh-clone", owner=owner)
        fake_docker_client.create_network(p)

        self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )

        self.assertIsNone(fake_docker_client.get_network(p))
        self.assertEqual(0, len(fake_docker_client.get_networks()))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClient(),
    )
    def test_with_nonexistent_network(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClient = mock_fake_docker.return_value
        p = Project.objects.create(slug="gh-clone", owner=owner)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNone(fake_docker_client.get_network(p))
