from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from ..models import Workspace, WorkspaceMembership, WorkspaceRole, Project
from .base import AuthAPITestCase
from ..utils import jprint


class EditWorkspaceUserPermissionsViewTests(AuthAPITestCase):
    def test_edit_user_permissions_in_workspace(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        data = {"role": WorkspaceRole.ADMIN}

        response = self.client.put(
            reverse(
                "zane_api:workspace.edit_membership_permissions",
                kwargs={"membership_id": membership.pk},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        membership = WorkspaceMembership.objects.get(
            user=user,
            workspace=workspace,
        )
        self.assertEqual(WorkspaceRole.ADMIN, membership.role)

    def test_edit_guest_user_permissions_in_workspace(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        data = {
            "role": WorkspaceRole.GUEST,
            "accessible_project_ids": [project.id],
        }

        response = self.client.put(
            reverse(
                "zane_api:workspace.edit_membership_permissions",
                kwargs={"membership_id": membership.pk},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        membership = WorkspaceMembership.objects.get(
            user=user,
            workspace=workspace,
        )
        self.assertEqual(WorkspaceRole.GUEST, membership.role)
        self.assertEqual(1, membership.accessible_projects.count())
        self.assertEqual(project, membership.accessible_projects.first())

    def test_cannot_edit_own_user_permissions(self):
        user = self.loginUser()

        membership = WorkspaceMembership.objects.get(user=user)

        data = {"role": WorkspaceRole.MEMBER}

        response = self.client.put(
            reverse(
                "zane_api:workspace.edit_membership_permissions",
                kwargs={"membership_id": membership.pk},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_edit_permissions_to_owner(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        data = {"role": WorkspaceRole.OWNER}

        response = self.client.put(
            reverse(
                "zane_api:workspace.edit_membership_permissions",
                kwargs={"membership_id": membership.pk},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "role"))
