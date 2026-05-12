from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from ..models import Workspace, WorkspaceMembership, WorkspaceRole
from .base import AuthAPITestCase
from ..utils import jprint


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

        # auth.me exposes the workspace; use it to verify which one is active
        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        membership = (
            WorkspaceMembership.objects.filter(user__username="Fredkiss3")
            .select_related("workspace")
            .get()
        )
        self.assertEqual(response.json()["workspace"]["id"], membership.workspace.id)

    def test_request_workspace_uses_session_key_when_set(self):
        user = self.loginUser()
        second_workspace = Workspace.objects.create(name="Second workspace", owner=user)
        WorkspaceMembership.objects.create(
            user=user, workspace=second_workspace, role=WorkspaceRole.ADMIN
        )
        self.client.post(
            reverse("zane_api:auth.switch_workspace"),
            data={"workspace_id": second_workspace.id},
        )

        # auth.me exposes the workspace; use it to verify which one is active
        response = self.client.get(reverse("zane_api:auth.me"))

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["workspace"]["id"], second_workspace.id)

    def test_request_workspace_falls_back_to_first_membership_without_session_key(self):
        user = self.loginUser()
        first_workspace = Workspace.objects.get(memberships__user=user)

        response = self.client.get(reverse("zane_api:auth.me"))

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json()["workspace"]["id"], first_workspace.id)

    def test_no_workspace_membership_returns_403(self):
        self.loginUser()
        WorkspaceMembership.objects.filter(user__username="Fredkiss3").delete()

        response = self.client.get(reverse("zane_api:auth.me"))

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class SwitchWorkspaceViewTests(AuthAPITestCase):
    def test_switch_workspace_sets_session_key(self):
        user = self.loginUser()
        second_workspace = Workspace.objects.create(name="Second workspace", owner=user)
        WorkspaceMembership.objects.create(
            user=user, workspace=second_workspace, role=WorkspaceRole.ADMIN
        )

        response = self.client.post(
            reverse("zane_api:auth.switch_workspace"),
            data={"workspace_id": second_workspace.id},
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(
            self.client.session.get("current_workspace_id"), second_workspace.id
        )

    def test_switch_workspace_not_a_member(self):
        self.loginUser()
        other_user = User.objects.create_user(username="other", password="password")
        other_workspace = Workspace.objects.create(
            name="Other workspace", owner=other_user
        )

        response = self.client.post(
            reverse("zane_api:auth.switch_workspace"),
            data={"workspace_id": other_workspace.id},
        )

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_switch_workspace_nonexistent(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:auth.switch_workspace"),
            data={"workspace_id": "wrk_doesnotexist"},
        )

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_switch_workspace_unauthenticated(self):
        response = self.client.post(
            reverse("zane_api:auth.switch_workspace"),
            data={"workspace_id": "wrk_doesnotexist"},
        )

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
