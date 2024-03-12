from dataclasses import dataclass
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock

import docker
import docker.errors
from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import Project
from ..services import get_network_resource_name


class FakeDockerClientWithNetworks:
    @dataclass
    class FakeNetwork:
        name: str
        parent: "FakeDockerClientWithNetworks"

        def remove(self):
            if self.parent.raise_error_on_delete:
                raise docker.errors.APIError("Unknow error when deleting network")
            self.parent.remove(self.name)

    def __init__(self, raise_error_on_create: bool = False, raise_error_on_delete: bool = False):
        self.networks = MagicMock()
        self.network_map = {}  # type: dict[str, FakeDockerClientWithNetworks.FakeNetwork]
        self.raise_error_on_create = raise_error_on_create
        self.raise_error_on_delete = raise_error_on_delete

        self.networks.create = self.docker_create_network
        self.networks.get = self.docker_get_network

    def docker_create_network(self, name: str, **kwargs):
        if self.raise_error_on_create:
            raise docker.errors.APIError('Unknown error when creating a network')

        created_network = FakeDockerClientWithNetworks.FakeNetwork(name, parent=self)
        self.network_map[name] = created_network
        return created_network

    def docker_get_network(self, name: str):
        network = self.network_map.get(name)

        if network is None:
            raise docker.errors.NotFound('network not found')
        return network

    def remove(self, name: str):
        network = self.network_map.pop(name)
        if network is None:
            raise docker.errors.NotFound('network not found')

    def get_network(self, p: Project):
        return self.network_map.get(get_network_resource_name(p))

    def create_network(self, p: Project):
        return self.docker_create_network(get_network_resource_name(p), scope="swarm", driver="overlay")

    def get_networks(self):
        return self.network_map


class ProjectListViewTests(AuthAPITestCase):
    def test_list_projects(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(owner=owner, name="Github Clone", slug="gh-clone"),
                Project(owner=owner, name="Thullo", slug="thullo"),
            ]
        )

        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)
        self.assertIsNotNone(project_list)

        assert type(project_list) is list
        assert len(project_list) == 2

    def test_default_no_include_archived(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, name="Thullo", slug="thullo", archived=True),
                Project(owner=owner, name="Github Clone", slug="gh-clone"),
            ]
        )
        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)
        self.assertEqual(1, len(project_list))

        found_archived_projects = list(
            filter(lambda p: p["archived"] == True, project_list)
        )
        self.assertEqual(0, len(found_archived_projects))

    def test_include_archived(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, name="Thullo", slug="thullo", archived=True),
                Project(owner=owner, name="Github Clone", slug="gh-clone"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="include_archived=true",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)
        self.assertEqual(1, len(project_list))

        found_archived_projects = list(
            filter(lambda p: p["archived"] == True, project_list)
        )
        self.assertNotEqual(0, len(found_archived_projects))

    def test_query_filter_projects_is_using_name_and_slug(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, name="Thullo", slug="thullo"),
                Project(owner=owner, name="Kiss Hub", slug="gh-clone"),
                Project(owner=owner, name="Camly", slug="kisscam"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="query=kiss",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)

        self.assertEqual(2, len(project_list))

    def test_sorting_projects_by_name(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, name="Thullo", slug="thullo", archived=True),
                Project(owner=owner, name="Github Clone", slug="gh-clone"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="sort=name_asc",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)
        self.assertEqual("gh-clone", project_list[0]["slug"])

    def test_sorting_projects_by_updated_at(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(
                    owner=owner,
                    name="Thullo",
                    slug="thullo",
                    archived=True,
                    updated_at=datetime(year=2022, month=2, day=5),
                ),
                Project(
                    owner=owner,
                    name="Github Clone",
                    slug="gh-clone",
                    updated_at=datetime(year=2024, month=1, day=2),
                ),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="sort=updated_at_desc",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)
        self.assertEqual("gh-clone", project_list[0]["slug"])

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class ProjectCreateViewTests(AuthAPITestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_sucessfully_create_project(self, _: Mock):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={
                "name": "Zane Ops",
            },
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())
        self.assertEqual("zane-ops", Project.objects.first().slug)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_bad_request(self, _: Mock):
        self.loginUser()
        response = self.client.post(reverse("zane_api:projects.list"), data={})
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        self.assertEqual(0, Project.objects.count())

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_unique_name(self, _: Mock):
        owner = self.loginUser()
        Project.objects.create(name="Zane Ops", slug="zane-ops", owner=owner)
        response = self.client.post(
            reverse("zane_api:projects.list"), data={"name": "Zane Ops"}
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, Project.objects.count())
        self.assertIsNotNone(response.json().get("errors", None))


class ProjectUpdateViewTests(AuthAPITestCase):
    def test_sucessfully_update_project_name(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(name="GH Clone", slug="gh-clone", owner=owner),
                Project(name="Zane Ops", slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"}),
            format="json",
            data={
                "name": "KissHub",
            },
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNotNone(updated_project)
        self.assertEqual("KissHub", updated_project.name)

    def test_bad_request(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(name="GH Clone", slug="gh-clone", owner=owner),
                Project(name="Zane Ops", slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

    def test_non_existent(self):
        self.loginUser()
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"name": "ZenOps"},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class ProjectGetViewTests(AuthAPITestCase):
    def test_sucessfully_get_project(self):
        owner = self.loginUser()
        Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner),
        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.json().get("project", None))

    def test_non_existent(self):
        self.loginUser()
        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class ProjectArchiveViewTests(AuthAPITestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_sucessfully_archive_project(self, _: Mock):
        owner = self.loginUser()
        Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner),
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNotNone(updated_project)
        self.assertEqual(True, updated_project.archived)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_non_existent(self, _: Mock):
        self.loginUser()
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_cannot_archive_already_archived_project(self, _: Mock):
        owner = self.loginUser()
        Project.objects.create(name="Zane Ops", slug="zane-ops", archived=True, owner=owner)
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks(raise_error_on_delete=True))
    def test_archive_with_error(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClientWithNetworks = mock_fake_docker.return_value
        p = Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner)
        fake_docker_client.create_network(p)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)

        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNotNone(updated_project)
        self.assertEqual(False, updated_project.archived)


class DockerAddNetworkTest(AuthAPITestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_network_is_created_on_new_project(self, mock_fake_docker: Mock):
        self.loginUser()
        # Create a new project
        self.client.post(
            reverse("zane_api:projects.list"),
            data={"name": "Zane Ops"},
        )

        p: Project | None = Project.objects.filter(slug="zane-ops").first()
        self.assertIsNotNone(mock_fake_docker.return_value.get_network(p))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks(raise_error_on_create=True))
    def test_error_when_creating_new_network(self, _: Mock):
        self.loginUser()
        # Create a new project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"name": "Zane Ops"},
        )

        self.assertEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)
        self.assertEqual(0, Project.objects.count())


class DockerRemoveNetworkTest(AuthAPITestCase):
    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_network_is_deleted_on_archived_project(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClientWithNetworks = mock_fake_docker.return_value
        p = Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner)
        fake_docker_client.create_network(p)

        self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertIsNone(fake_docker_client.get_network(p))
        self.assertEqual(0, len(fake_docker_client.get_networks()))

    @patch("zane_api.services.get_docker_client", return_value=FakeDockerClientWithNetworks())
    def test_with_nonexistent_network(self, mock_fake_docker: Mock):
        owner = self.loginUser()
        fake_docker_client: FakeDockerClientWithNetworks = mock_fake_docker.return_value
        p = Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNone(fake_docker_client.get_network(p))
