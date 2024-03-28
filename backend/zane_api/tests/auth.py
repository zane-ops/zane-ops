from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase, APITestCase


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
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)


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
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)


class CSRFViewTests(APITestCase):
    def test_sucessful(self):
        response = self.client.get(reverse("zane_api:csrf"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(
            response.cookies.get("csrftoken"),
        )
