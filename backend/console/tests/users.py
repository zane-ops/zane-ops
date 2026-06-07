from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from console.models import PasswordResetToken


class GeneratePasswordResetCodeViewTests(AuthAPITestCase):
    def test_instance_owner_can_generate_password_reset_code(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        token = cast(
            PasswordResetToken, PasswordResetToken.objects.filter(user=user).first()
        )
        self.assertIsNotNone(token)

    def test_generate_password_reset_code_replaces_existing_one(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        first_token_value = cast(
            PasswordResetToken, PasswordResetToken.objects.get(user=user)
        ).value

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        self.assertEqual(1, PasswordResetToken.objects.filter(user=user).count())
        new_token_value = cast(
            PasswordResetToken, PasswordResetToken.objects.get(user=user)
        ).value
        self.assertNotEqual(first_token_value, new_token_value)

    def test_non_instance_owner_cannot_generate_password_reset_code(self):
        user = User.objects.create_user(username="mohai", password="password")

        self.client.login(username="mohai", password="password")

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_generate_password_reset_code_for_nonexistent_user(self):
        self.loginUser()

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": 99999})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class ResetUserPasswordViewTests(AuthAPITestCase):
    def test_user_can_reset_password_with_valid_token(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="old_password")

        self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        token = cast(
            PasswordResetToken, PasswordResetToken.objects.get(user=user)
        ).value

        self.client.logout()

        response = self.client.post(
            reverse("zane_api:auth.reset_password", kwargs={"token": token}),
            data={
                "new_password": "new_password123",
                "confirm_password": "new_password123",
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        user.refresh_from_db()
        self.assertTrue(user.check_password("new_password123"))
        self.assertIsNone(PasswordResetToken.objects.filter(user=user).first())

    def test_reset_password_token_is_single_use(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="old_password")

        self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        token = cast(
            PasswordResetToken, PasswordResetToken.objects.get(user=user)
        ).value

        self.client.logout()

        self.client.post(
            reverse("zane_api:auth.reset_password", kwargs={"token": token}),
            data={
                "new_password": "new_password123",
                "confirm_password": "new_password123",
            },
        )

        response = self.client.post(
            reverse("zane_api:auth.reset_password", kwargs={"token": token}),
            data={
                "new_password": "another_password123",
                "confirm_password": "another_password123",
            },
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_reset_password_with_invalid_token(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:auth.reset_password", kwargs={"token": "invalid-token"}),
            data={
                "new_password": "new_password123",
                "confirm_password": "new_password123",
            },
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_reset_password_with_mismatched_passwords(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="old_password")

        self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        token = cast(
            PasswordResetToken, PasswordResetToken.objects.get(user=user)
        ).value

        self.client.logout()

        response = self.client.post(
            reverse("zane_api:auth.reset_password", kwargs={"token": token}),
            data={
                "new_password": "new_password123",
                "confirm_password": "different_password123",
            },
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
