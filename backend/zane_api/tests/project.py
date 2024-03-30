import datetime
from dataclasses import dataclass
from unittest.mock import patch, Mock, MagicMock

import docker
import docker.errors
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..docker_operations import get_network_resource_name
from ..models import Project, ArchivedProject


class FakeDockerClientWithNetworks:
    @dataclass
    class FakeNetwork:
        name: str
        id: str
        parent: "FakeDockerClientWithNetworks"

        def remove(self):
            if self.parent.raise_error_on_delete:
                raise docker.errors.APIError("Unknow error when deleting network")
            self.parent.remove(self.name)

    class FakeService:
        def __init__(self):
            self.attrs = {
                "Spec": {
                    "TaskTemplate": {
                        "Networks": [],
                    },
                }
            }

        def update(self, networks: list):
            self.attrs["Spec"]["TaskTemplate"]["Networks"] = [
                {"Target": network} for network in networks
            ]

    def __init__(
        self, raise_error_on_create: bool = False, raise_error_on_delete: bool = False
    ):
        self.services = MagicMock()
        self.networks = MagicMock()
        self.network_map = (
            {}
        )  # type: dict[str, FakeDockerClientWithNetworks.FakeNetwork]
        self.raise_error_on_create = raise_error_on_create
        self.raise_error_on_delete = raise_error_on_delete

        self.networks.create = self.docker_create_network
        self.networks.get = self.docker_get_network

        self.proxy_service = FakeDockerClientWithNetworks.FakeService()
        self.services.get.return_value = self.proxy_service

    def docker_create_network(self, name: str, **kwargs):
        if self.raise_error_on_create:
            raise docker.errors.APIError("Unknown error when creating a network")

        created_network = FakeDockerClientWithNetworks.FakeNetwork(
            name=name, id=name, parent=self
        )
        self.network_map[name] = created_network
        return created_network

    def docker_get_network(self, name: str):
        network = self.network_map.get(name)

        if network is None:
            raise docker.errors.NotFound("network not found")
        return network

    def remove(self, name: str):
        network = self.network_map.pop(name)
        if network is None:
            raise docker.errors.NotFound("network not found")

    def get_network(self, p: Project):
        return self.network_map.get(get_network_resource_name(p.id))

    def create_network(self, p: Project):
        return self.docker_create_network(
            get_network_resource_name(p.id),
            scope="swarm",
            driver="overlay",
        )

    def get_networks(self):
        return self.network_map


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
        return_value=FakeDockerClientWithNetworks(),
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
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_generate_slug_if_not_specified(self, _: Mock):
        self.loginUser()
        response = self.client.post(reverse("zane_api:projects.list"), data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())
        self.assertIsNotNone(Project.objects.filter().first().slug)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_unique_slug(self, _: Mock):
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertIsNotNone(response.json().get("errors"))
        self.assertEqual(1, Project.objects.count())

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_invalid_slug(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane Ops"},
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        self.assertIsNotNone(response.json().get("errors"))
        self.assertIsNotNone(response.json().get("errors").get("slug"))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
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
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        self.assertIsNotNone(response.json().get("errors").get("slug"))

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
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_sucessfully_archive_project(self, _: Mock):
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

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_non_existent(self, _: Mock):
        self.loginUser()
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_cannot_archive_already_archived_project(self, _: Mock):
        owner = self.loginUser()
        ArchivedProject.objects.create(slug="zane-ops", owner=owner)
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_cannot_reuse_archived_version_if_it_exists(self, _: Mock):
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


class DockerAddNetworkTest(AuthAPITestCase):
    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
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
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_network_is_deleted_on_archived_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClientWithNetworks = mock_fake_docker.return_value
        p = Project.objects.create(slug="gh-clone", owner=owner)
        fake_docker_client.create_network(p)

        self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )

        self.assertIsNone(fake_docker_client.get_network(p))
        self.assertEqual(0, len(fake_docker_client.get_networks()))

    @patch(
        "zane_api.docker_operations.get_docker_client",
        return_value=FakeDockerClientWithNetworks(),
    )
    def test_with_nonexistent_network(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClientWithNetworks = mock_fake_docker.return_value
        p = Project.objects.create(slug="gh-clone", owner=owner)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNone(fake_docker_client.get_network(p))
