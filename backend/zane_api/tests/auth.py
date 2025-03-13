from datetime import timedelta
from unittest.mock import patch, Mock

from django.conf import settings
from django.contrib.auth.models import User
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token

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

    def test_sucessful_login_create_token(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "Fredkiss3", "password": "password"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(
            response.cookies.get("sessionid"),
        )
        user = User.objects.get(username="Fredkiss3")
        self.assertIsNotNone(Token.objects.filter(user=user).first())

    def test_login_redirect_to_if_provided(self):
        params = QueryDict(mutable=True)
        redirect_path = "https://example-service-dpl_xyz.zaneops.local/"
        params["redirect_to"] = redirect_path

        response = self.client.post(
            f"{reverse('zane_api:auth.login')}?{params.urlencode()}",
            data={"username": "Fredkiss3", "password": "password"},
        )
        self.assertEqual(status.HTTP_302_FOUND, response.status_code)
        self.assertIsNotNone(
            response.cookies.get("sessionid"),
        )
        self.assertEqual(
            redirect_path,
            response.headers.get("Location"),
        )

    def test_unsucessful_login(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "user", "password": "bad_password"},
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_bad_request(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_login_ratelimit(self):
        for _ in range(6):
            response = self.client.post(
                reverse("zane_api:auth.login"),
                data={},
            )
        self.assertEqual(status.HTTP_429_TOO_MANY_REQUESTS, response.status_code)


class AuthMeViewTests(AuthAPITestCase):
    def test_authed(self):
        self.loginUser()
        response = self.client.get(reverse("zane_api:auth.me"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.json().get("user"))
        user = response.json().get("user")
        self.assertEqual("Fredkiss3", user["username"])

    def test_authed_with_token(self):
        user = User.objects.get(username="Fredkiss3")
        token, _ = Token.objects.get_or_create(user=user)
        response = self.client.get(
            reverse("zane_api:auth.me.with_token"),
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.json().get("user"))
        user = response.json().get("user")
        self.assertEqual("Fredkiss3", user["username"])

    @patch("zane_api.views.auth.timezone")
    def test_authed_renew_session(self, mock_timezone: Mock):
        self.loginUser()

        fixed_time = timezone.now() + timedelta(days=13)
        mock_timezone.now.return_value = fixed_time
        response = self.client.get(reverse("zane_api:auth.me"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.cookies.get("sessionid"))

    def test_authed_without_token_but_session(self):
        self.loginUser()
        response = self.client.get(
            reverse("zane_api:auth.me.with_token"),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_unauthed_without_token_and_session(self):
        response = self.client.get(
            reverse("zane_api:auth.me.with_token"),
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_unauthed_with_bad_token(self):
        response = self.client.get(
            reverse("zane_api:auth.me.with_token"),
            HTTP_AUTHORIZATION=f"Token bad_token",
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:auth.me"))
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_redirect_token_to_path_if_html_request_if_not_authed(self):
        response = self.client.get(
            reverse("zane_api:auth.me.with_token"),
            content_type="application/json",
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(status.HTTP_302_FOUND, response.status_code)

    def test_redirect_to_path_if_html_request_if_not_authed_for_proxy(self):
        response = self.client.get(
            reverse("zane_api:auth.me.with_token"),
            content_type="application/json",
            HTTP_ACCEPT="text/html",
            HTTP_HOST=f"example-service-dpl-xyz.{settings.ROOT_DOMAIN}",
            HTTP_X_FORWARED_URI="/",
            HTTP_X_FORWARED_PROTO="https",
        )
        self.assertEqual(status.HTTP_302_FOUND, response.status_code)
        params = QueryDict(mutable=True)
        params["redirect_to"] = (
            f"https://example-service-dpl-xyz.{settings.ROOT_DOMAIN}/"
        )

        self.assertEqual(
            f"{reverse('zane_api:auth.login')}?{params.urlencode()}",
            response.headers.get("Location"),
        )


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


class UserExistenceAndCreationTests(APITestCase):
    def test_check_user_existence_no_user(self):
        response = self.client.get(reverse("zane_api:check-user-existence"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("exists"), False)

    def test_check_user_existence_with_user(self):
        User.objects.create_user(username="mocherif", password="mocherif")
        response = self.client.get(reverse("zane_api:check-user-existence"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("exists"), True)

    def test_create_user_success(self):
        response = self.client.post(
            reverse("zane_api:create-user"),
            data={"username": "mohai", "password": "mohai123"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertTrue(User.objects.filter(username="mohai").exists())
        self.assertIsNotNone(response.cookies.get("sessionid"))

    def test_create_user_already_exists(self):
        User.objects.create_user(username="mohai", password="mohai123")
        response = self.client.post(
            reverse("zane_api:create-user"),
            data={"username": "fred", "password": "fred123"},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_create_user_bad_request(self):
        response = self.client.post(reverse("zane_api:create-user"), data={})
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_user_minimum_password_length(self):
        response = self.client.post(
            reverse("zane_api:create-user"),
            data={"username": "mohai", "password": "123"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_user_minimum_username_length(self):
        response = self.client.post(
            reverse("zane_api:create-user"),
            data={"username": "", "password": "validpassword123"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
