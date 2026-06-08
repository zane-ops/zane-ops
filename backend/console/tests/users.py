from datetime import timedelta
from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
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

    def test_instance_owner_cannot_generate_password_reset_code_for_oneself(self):
        me = self.loginUser()

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": me.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

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

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

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

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

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
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_reset_password_with_invalid_token(self):
        self.loginUser()

        response = self.client.post(
            reverse(
                "zane_api:auth.reset_password", kwargs={"token": "invalidtoken123"}
            ),
            data={
                "new_password": "new_password123",
                "confirm_password": "new_password123",
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_reset_password_with_mismatched_passwords(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="old_password")

        response = self.client.post(
            reverse("console:user.generate_password_reset", kwargs={"id": user.pk})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

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
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "confirm_password"))

    def test_reset_password_with_expired_token(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="old_password")
        token = PasswordResetToken.objects.create(
            user=user,
            value="expiredtoken123",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        self.client.logout()

        response = self.client.post(
            reverse("zane_api:auth.reset_password", kwargs={"token": token.value}),
            data={
                "new_password": "new_password123",
                "confirm_password": "new_password123",
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class ToggleUserStatusViewTests(AuthAPITestCase):
    def test_suspend_user(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")
        response = self.client.patch(
            reverse("console:user.details", kwargs={"id": user.pk}),
            data={"is_active": False},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_reactivate_user(self):
        self.loginUser()

        user = User.objects.create_user(
            username="mohai", password="password", is_active=False
        )
        response = self.client.patch(
            reverse("console:user.details", kwargs={"id": user.pk}),
            data={"is_active": True},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_non_instance_owner_cannot_toggle_user_status(self):
        user = User.objects.create_user(username="mohai", password="password")
        self.client.login(username="mohai", password="password")

        response = self.client.patch(
            reverse("console:user.details", kwargs={"id": user.pk}),
            data={"is_active": False},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_cannot_toggle_own_status(self):
        self.loginUser()

        me = User.objects.get(username="Fredkiss3")
        response = self.client.patch(
            reverse("console:user.details", kwargs={"id": me.pk}),
            data={"is_active": False},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_toggle_status_for_nonexistent_user(self):
        self.loginUser()

        response = self.client.patch(
            reverse("console:user.details", kwargs={"id": 99999}),
            data={"is_active": False},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_suspending_user_clears_their_sessions(self):
        user = User.objects.create_user(username="mohai", password="password")

        mohai_client = self.client_class()
        mohai_client.login(username="mohai", password="password")

        self.loginUser()
        self.client.patch(
            reverse("console:user.details", kwargs={"id": user.pk}),
            data={"is_active": False},
        )

        response = mohai_client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_suspended_user_cannot_login(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")
        self.client.patch(
            reverse("console:user.details", kwargs={"id": user.pk}),
            data={"is_active": False},
        )
        self.client.logout()

        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "mohai", "password": "password"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
