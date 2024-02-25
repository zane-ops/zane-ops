from datetime import datetime
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache

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
        return User.objects.create_user(username="Fredkiss3", password="password")

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
        self.assertDictContainsSubset(
            {"username": "Fredkiss3"}, response.json().get("user")
        )

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
            QUERY_STRING="include_archived",
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
                Project(owner=owner, name="Github Clone", slug="gh-clone"),
                Project(owner=owner, name="Locaci", slug="csdev-locaci"),
                Project(owner=owner, name="CSDEV Ledjassa", slug="ledjassa"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="query=csdev",
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
            QUERY_STRING="sort=name",
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
            QUERY_STRING="sort=updated_at",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("projects", None)
        self.assertEqual("thullo", project_list[0]["slug"])

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
