from time import sleep
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
        }
    },
)
class APITestCase(TestCase):
    client = APIClient()

    def tearDown(self):
        cache.clear()


class AuthLoginViewTests(APITestCase):
    def setUp(self):
        User.objects.create_user(username="user", password="password")

    def test_sucessful_login(self):
        response = self.client.post(
            reverse("zane_api:auth_login"),
            data={"username": "user", "password": "password"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(
            response.cookies.get("sessionid"),
        )

    def test_unsucessful_login(self):
        response = self.client.post(
            reverse("zane_api:auth_login"),
            data={"username": "user", "password": "bad_password"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIsNotNone(response.json().get("errors", None))

    def test_bad_request(self):
        response = self.client.post(
            reverse("zane_api:auth_login"),
            data={},
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        errors = response.json().get("errors", None)

        self.assertIsNotNone(errors)
        self.assertIn("username", errors)
        self.assertIn("password", errors)

    def test_login_ratelimit(self):
        for _ in range(6):
            response = self.client.post(
                reverse("zane_api:auth_login"),
                data={},
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIsNotNone(response.json().get("errors", None))


class AuthMeViewTests(APITestCase):
    def setUp(self):
        User.objects.create_user(username="user", password="password")

    def test_authed(self):
        self.client.login(username="user", password="password")
        response = self.client.get(reverse("zane_api:auth_me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:auth_me"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
