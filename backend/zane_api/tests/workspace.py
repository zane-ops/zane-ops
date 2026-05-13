from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from ..models import Workspace, WorkspaceMembership, WorkspaceRole
from .base import AuthAPITestCase, APITestCase
from ..utils import jprint
from ..constants import WORKSPACE_SESSION_KEY


class OnBoardingTests(APITestCase):
    def test_create_initial_user_creates_default_workspace_without_providing_workspace_name(
        self,
    ):
        response = self.client.post(
            reverse("zane_api:auth.create_initial_user"),
            data={
                "username": "mohai",
                "password": "mohai123",
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        default_user = cast(User, User.objects.filter(username="mohai").first())
        self.assertIsNotNone(default_user)

        default_workspace = cast(Workspace, Workspace.objects.first())
        self.assertIsNotNone(default_workspace)

        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                workspace=default_workspace, user=default_user
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(WorkspaceRole.OWNER, membership.role)

    def test_create_initial_user_with_custom_workspace_name(self):
        response = self.client.post(
            reverse("zane_api:auth.create_initial_user"),
            data={
                "username": "mohai",
                "password": "mohai123",
                "workspace_name": "Custom workspace",
            },
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        default_user = cast(User, User.objects.filter(username="mohai").first())
        self.assertIsNotNone(default_user)

        default_workspace = cast(
            Workspace, Workspace.objects.filter(name="Custom workspace").first()
        )
        self.assertIsNotNone(default_workspace)

        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                workspace=default_workspace, user=default_user
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(WorkspaceRole.OWNER, membership.role)


class WorkspaceMiddlewareTests(AuthAPITestCase):
    def test_cannot_login_without_being_a_workspace_member(self):
        User.objects.create_user(username="mohai", password="password")

        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "mohai", "password": "password"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_set_workspace_when_login(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "Fredkiss3", "password": "password"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify that workspace session is set
        self.assertIsNotNone(self.client.session.get(WORKSPACE_SESSION_KEY))

        # auth.me exposes the workspace; use it to verify which one is active
        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        workspace = Workspace.objects.filter(
            memberships__user__username="Fredkiss3"
        ).get()

        self.assertEqual(response.json()["membership"]["workspace"]["id"], workspace.id)

    def test_request_workspace_falls_back_to_first_membership_without_session_key(self):
        user = self.loginUser()  # manual login doesn't set the workspace in the session

        self.assertIsNone(self.client.session.get(WORKSPACE_SESSION_KEY))

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(user=user, workspace=second_workspace)

        first_workspace = Workspace.objects.filter(memberships__user=user).earliest(
            "created_at"
        )

        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            response.json()["membership"]["workspace"]["id"], first_workspace.id
        )


class EditWorkspaceTests(AuthAPITestCase):
    def test_can_edit_workspace_if_owner(self):
        self.loginUser()

        response = self.client.put(
            reverse("zane_api:workspaces.edit"),
            data={"name": "Fredkiss corp"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_cannot_edit_workspace_if_not_at_least_admin(self):
        user = self.loginUser()

        user.is_superuser = False
        user.save()
        WorkspaceMembership.objects.filter(user=user).update(role=WorkspaceRole.MEMBER)

        response = self.client.put(
            reverse("zane_api:workspaces.edit"),
            data={"name": "Fredkiss corp"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_can_edit_workspace_if_admin(self):
        user = self.loginUser()

        user.is_superuser = False
        user.save()
        WorkspaceMembership.objects.filter(user=user).update(role=WorkspaceRole.ADMIN)

        response = self.client.put(
            reverse("zane_api:workspaces.edit"),
            data={"name": "Fredkiss corp"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class CreateWorkspaceTests(AuthAPITestCase):
    def test_create_workspace_successful(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspaces.create"),
            data={"name": "Fredkiss's work"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

    def test_cannot_create_workspace_if_not_instance_admin(self):
        user = self.loginUser()
        user.is_superuser = False
        user.save()

        response = self.client.post(
            reverse("zane_api:workspaces.create"),
            data={"name": "Fredkiss's work"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class SwitchWorkspaceViewTests(AuthAPITestCase):
    def test_switch_workspace_sets_session_key(self):
        user = self.loginUser()

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=second_workspace, role=WorkspaceRole.ADMIN
        )

        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": second_workspace.id},
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(
            self.client.session.get(WORKSPACE_SESSION_KEY), second_workspace.id
        )

        # auth.me exposes the workspace; use it to verify which one is active
        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            response.json()["membership"]["workspace"]["id"], second_workspace.id
        )

    def test_cannot_switch_to_a_workspace_without_being_a_member(self):
        self.loginUser()

        other_workspace = Workspace.objects.create(name="Other workspace")

        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": other_workspace.id},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_switch_workspace_nonexistent(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": "wrk_doesnotexist"},
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_switch_workspace_unauthenticated(self):
        workspace = cast(Workspace, Workspace.objects.first())
        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": workspace.id},
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
