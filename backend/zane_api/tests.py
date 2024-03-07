from datetime import datetime
from typing import Any
from unittest.mock import patch, Mock

import docker
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Project


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
)
class APITestCase(TestCase):
    client = APIClient(enforce_csrf_checks=True)

    def tearDown(self):
        cache.clear()


class AuthAPITestCase(APITestCase):
    def setUp(self):
        User.objects.create_user(username="Fredkiss3", password="password")

    def loginUser(self):
        self.client.login(username="Fredkiss3", password="password")
        return User.objects.get(username="Fredkiss3")


class AuthLoginViewTests(AuthAPITestCase):
    def test_sucessful_login(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "Fredkiss3", "password": "password"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(
            response.cookies.get("sessionid"),
        )

    def test_unsucessful_login(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "user", "password": "bad_password"},
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
        self.assertIsNotNone(response.json().get("errors", None))

    def test_bad_request(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={},
        )
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        errors = response.json().get("errors", None)

        self.assertIsNotNone(errors)
        self.assertIn("username", errors)
        self.assertIn("password", errors)

    def test_login_ratelimit(self):
        for _ in range(6):
            response = self.client.post(
                reverse("zane_api:auth.login"),
                data={},
            )
        self.assertEqual(status.HTTP_429_TOO_MANY_REQUESTS, response.status_code)
        self.assertIsNotNone(response.json().get("errors", None))


class AuthMeViewTests(AuthAPITestCase):
    def test_authed(self):
        self.loginUser()
        response = self.client.get(reverse("zane_api:auth.me"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.json().get("user", None))
        user = response.json().get("user")
        self.assertEqual("Fredkiss3", user["username"])

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:auth.me"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class AuthLogoutViewTests(AuthAPITestCase):
    def test_sucessful_logout(self):
        self.loginUser()
        response = self.client.delete(reverse("zane_api:auth.logout"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNotNone(
            response.cookies.get("sessionid"),
        )

    def test_unsucessful_logout(self):
        response = self.client.delete(reverse("zane_api:auth.logout"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class CSRFViewTests(APITestCase):
    def test_sucessful(self):
        response = self.client.get(reverse("zane_api:csrf"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(
            response.cookies.get("csrftoken"),
        )


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
    @patch("zane_api.services.docker.from_env")
    def test_sucessfully_create_project(self, _: Any):
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

    def test_bad_request(self):
        self.loginUser()
        response = self.client.post(reverse("zane_api:projects.list"), data={})
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        self.assertEqual(0, Project.objects.count())

    @patch("zane_api.services.docker.from_env")
    def test_unique_name(self, _: Any):
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
        updated_project = Project.objects.get(slug="gh-clone")
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
    def test_sucessfully_archive_project(self):
        owner = self.loginUser()
        Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner),
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        updated_project = Project.objects.get(slug="gh-clone")
        self.assertIsNotNone(updated_project)
        self.assertEqual(True, updated_project.archived)

    def test_non_existent(self):
        self.loginUser()
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DockerViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.loginUser()

    @patch("zane_api.views.docker.DockerService")
    def test_search_docker_images(self, mock_docker_client: Any):
        # Mock the response of the Docker SDK
        mock_response = [
            {
                "name": "caddy",
                "is_official": True,
                "is_automated": True,
                "description": "Caddy 2 is a powerful, enterprise-ready, open source web server with automatic HTTPS written in Go",
            },
            {
                "description": "caddy webserver optimized for usage within the SIWECOS project",
                "is_automated": False,
                "is_official": False,
                "name": "siwecos/caddy",
                "star_count": 0,
            },
        ]
        mock_docker_client.search_registry.return_value = mock_response
        response = self.client.get(
            reverse("zane_api:docker.image_search"), QUERY_STRING="q=caddy"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify that the Docker SDK was called with the correct query
        mock_docker_client.search_registry.assert_called_once_with(term="caddy")

        self.assertIsNotNone(response.json().get("images"))
        images = response.json().get("images")
        self.assertEqual(images[0]["full_image"], "library/caddy:latest")
        self.assertEqual(images[1]["full_image"], "siwecos/caddy:latest")

    @patch("zane_api.views.docker.DockerService")
    def test_search_query_empty(self, mock_docker_client: Any):
        response = self.client.get(reverse("zane_api:docker.image_search"))
        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)
        mock_docker_client.search_registry.assert_not_called()

    @patch("zane_api.views.docker.DockerService")
    def test_success_validate_credentials(self, mock_docker_client: Any):
        mock_docker_client.login.return_value = True
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "username": "user",
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify that the Docker SDK was called with the correct query
        mock_docker_client.login.assert_called_once_with(
            username="user", password="password"
        )

    @patch("zane_api.views.docker.DockerService")
    def test_bad_credentials(self, mock_docker_client: Any):
        mock_docker_client.login.return_value = False
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "username": "user",
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

        # Verify that the Docker SDK was called with the correct query
        mock_docker_client.login.assert_called_once_with(
            username="user", password="password"
        )

    @patch("zane_api.views.docker.DockerService")
    def test_bad_request_for_credentials(self, mock_docker_client: Any):
        response = self.client.post(
            reverse("zane_api:docker.login"),
            data={
                "password": "password",
            },
        )

        self.assertEqual(status.HTTP_422_UNPROCESSABLE_ENTITY, response.status_code)

        # Verify that the Docker SDK was called with the correct query
        mock_docker_client.login.assert_not_called()


class FakeDockerService:
    @classmethod
    def check_if_port_is_available(cls, port: int) -> bool:
        return port != 90


class DockerPortMappingViewTests(AuthAPITestCase):
    @patch("zane_api.views.docker.DockerService", wraps=FakeDockerService)
    def test_successfull(self, _: Any):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 8080,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), True)

    @patch("zane_api.views.docker.DockerService", wraps=FakeDockerService)
    def test_unavailable_port(self, _: Any):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 90,
            },
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(response.json().get("available"), False)


class FakeNetwork:
    def __init__(self, name: str):
        self.name = name

    def remove(self):
        FakeDockerNetworks.networks.pop(self.name)


class FakeDockerNetworks:
    networks: dict[str, FakeNetwork] = {}
    raise_error = False

    @classmethod
    def create(cls, name: str):
        if cls.raise_error:
            raise docker.errors.APIError('Unknown error')
        created_network = FakeNetwork(name)
        cls.networks[name] = created_network
        return created_network

    @classmethod
    def get(cls, name: str):
        network = cls.networks.get(name)

        if network is None:
            raise docker.errors.NotFound('network not found')
        return network


class FakeDockerClientWithNetworks:
    networks = FakeDockerNetworks()


class DockerAddNetworkTest(AuthAPITestCase):
    @patch("zane_api.services.docker.from_env")
    def test_network_is_created_on_new_project(self, mock_fake_docker: Mock):
        self.loginUser()
        mock_fake_docker.return_value = FakeDockerClientWithNetworks()

        # Create a new project
        self.client.post(
            reverse("zane_api:projects.list"),
            data={"name": "Zane Ops"},
        )

        p = Project.objects.get(slug="zane-ops")
        self.assertIsNotNone(FakeDockerNetworks.networks.get(f'zane-ops-{p.created_at.timestamp()}'))

    @patch("zane_api.services.docker.from_env")
    def test_error_when_creating_new_network(self, mock_fake_docker: Mock):
        self.loginUser()
        mock_fake_docker.return_value = FakeDockerClientWithNetworks()
        FakeDockerNetworks.raise_error = True

        # Create a new project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"name": "Zane Ops"},
        )

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(0, Project.objects.count())


class DockerRemoveNetworkTest(AuthAPITestCase):
    @patch("zane_api.services.docker.from_env")
    def test_network_is_deleted_on_archived_project(self, mock_fake_docker: Any):
        owner = self.loginUser()
        mock_fake_docker.return_value = FakeDockerClientWithNetworks()
        p = Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner)
        FakeDockerNetworks.create(f'gh-clone-{p.created_at.timestamp()}')

        self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertIsNone(FakeDockerNetworks.networks.get(f'gh-clone-{p.created_at.timestamp()}'))
        self.assertEqual(0, len(FakeDockerNetworks.networks.keys()))

    @patch("zane_api.services.docker.from_env")
    def test_with_nonexistent_network(self, mock_fake_docker: Any):
        owner = self.loginUser()
        mock_fake_docker.return_value = FakeDockerClientWithNetworks()
        p = Project.objects.create(name="GH Clone", slug="gh-clone", owner=owner)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNone(FakeDockerNetworks.networks.get(f'gh-clone-{p.created_at.timestamp()}'))
