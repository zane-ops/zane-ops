from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from ..models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    Project,
    WorkspaceInvitation,
)
from .base import AuthAPITestCase, APITestCase
from ..utils import jprint
from django.utils import timezone
from datetime import timedelta


class WorkspaceInviteUserViewTests(AuthAPITestCase):
    def test_invite_new_user_default(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        data = {"username": "mohai"}
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())
        self.assertIsNotNone(new_invitation)
        self.assertEqual(new_invitation.role, WorkspaceRole.MEMBER)
        self.assertEqual(new_invitation.username, "mohai")
        self.assertEqual(new_invitation.workspace, workspace)

        now = timezone.now()
        self.assertAlmostEqual(
            new_invitation.expires_at,
            now + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

    def test_invite_new_user_customized(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        data = {
            "username": "mohai",
            "valid_for": 5,
            "role": WorkspaceRole.ADMIN,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())
        self.assertIsNotNone(new_invitation)
        self.assertEqual(new_invitation.role, WorkspaceRole.ADMIN)
        self.assertEqual(new_invitation.username, "mohai")
        self.assertEqual(new_invitation.workspace, workspace)

        now = timezone.now()
        self.assertAlmostEqual(
            new_invitation.expires_at,
            now + timedelta(days=5),
            delta=timedelta(seconds=5),
        )

    def test_invite_with_guest_role(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")

        data = {
            "username": "mohai",
            "role": WorkspaceRole.GUEST,
            "accessible_project_ids": [project.id],
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())
        self.assertIsNotNone(new_invitation)
        self.assertEqual(1, new_invitation.accessible_projects.count())
        self.assertEqual(project, new_invitation.accessible_projects.first())

    def test_invite_user_with_role_greater_than_guest_empties_accessible_projects(
        self,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")

        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
            "accessible_project_ids": [project.id],
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())
        self.assertIsNotNone(new_invitation)
        self.assertEqual(0, new_invitation.accessible_projects.count())

    def test_invite_user_with_guest_permission_require_nonempty_accessible_projects(
        self,
    ):
        self.loginUser()
        data = {
            "username": "mohai",
            "role": WorkspaceRole.GUEST,
            "accessible_project_ids": [],
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "accessible_project_ids")
        )

    def test_cannot_invite_user_with_owner_role(self):
        self.loginUser()
        data = {
            "username": "mohai",
            "role": WorkspaceRole.OWNER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "role"))

    def test_invite_user_cannot_select_accessible_project_not_in_current_workspace(
        self,
    ):
        user = self.loginUser()
        first_workspace = cast(Workspace, Workspace.objects.first())

        # 1- switch to 2nd workspace
        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=second_workspace, role=WorkspaceRole.ADMIN
        )
        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": second_workspace.id},
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # 2- create project in 2nd workspace
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")
        self.assertEqual(project.workspace, second_workspace)

        # 3- switch back to 1st workspace
        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": first_workspace.id},
        )

        # 4- Try to invite user with accesible project from other workspace
        data = {
            "username": "mohai",
            "role": WorkspaceRole.GUEST,
            "accessible_project_ids": [project.id],
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "accessible_project_ids")
        )

    def test_require_minimal_workspace_admin_permission_to_invite_user(self):
        owner = self.loginUser()
        WorkspaceMembership.objects.filter(user=owner).update(role=WorkspaceRole.MEMBER)
        # 4- Try to invite user with accesible project from other workspace
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_cannot_invite_two_users_with_the_same_username(self):
        self.loginUser()
        data = {"username": "mohai"}
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        data = {"username": "mohai"}
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
