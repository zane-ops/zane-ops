from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from ..models import Workspace, WorkspaceMembership, WorkspaceRole, Project
from ..constants import WORKSPACE_SESSION_KEY
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

    def test_edit_guest_accessible_projects(self):
        self.loginUser()
        for slug in ["zaneops", "second-project"]:
            response = self.client.post(
                reverse("zane_api:projects.list"),
                data={"slug": slug, "env_slug": "production"},
            )
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        first_project = Project.objects.get(slug="zaneops")
        second_project = Project.objects.get(slug="second-project")

        workspace = cast(Workspace, Workspace.objects.first())
        user = User.objects.create_user(username="mohai", password="password")
        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.GUEST,
            user=user,
            workspace=workspace,
        )
        membership.accessible_projects.set([first_project])

        data = {
            "role": WorkspaceRole.GUEST,
            "accessible_project_ids": [second_project.id],
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

        membership = WorkspaceMembership.objects.get(user=user, workspace=workspace)
        self.assertEqual(1, membership.accessible_projects.count())
        self.assertEqual(second_project, membership.accessible_projects.first())

    def test_edit_permissions_with_role_greater_than_guest_empties_accessible_projects(
        self,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.GUEST,
            user=user,
            workspace=workspace,
        )
        membership.accessible_projects.set([project])

        data = {
            "role": WorkspaceRole.MEMBER,
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

        membership = WorkspaceMembership.objects.get(user=user, workspace=workspace)
        self.assertEqual(0, membership.accessible_projects.count())

    def test_edit_guest_permissions_require_nonempty_accessible_projects(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        data = {
            "role": WorkspaceRole.GUEST,
            "accessible_project_ids": [],
        }

        response = self.client.put(
            reverse(
                "zane_api:workspace.edit_membership_permissions",
                kwargs={"membership_id": membership.pk},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "accessible_project_ids")
        )

    def test_cannot_select_accessible_project_not_in_current_workspace(self):
        user = self.loginUser()
        first_workspace = cast(Workspace, Workspace.objects.first())

        # switch to 2nd workspace
        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=second_workspace, role=WorkspaceRole.ADMIN
        )
        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": second_workspace.id},
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # create project in 2nd workspace
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")
        self.assertEqual(project.workspace, second_workspace)

        # switch back to 1st workspace
        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": first_workspace.id},
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        other_user = User.objects.create_user(username="mohai", password="password")
        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=other_user,
            workspace=first_workspace,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "accessible_project_ids")
        )

    def test_require_minimal_workspace_admin_permission_to_edit_user_permissions(self):
        owner = self.loginUser()
        WorkspaceMembership.objects.filter(user=owner).update(role=WorkspaceRole.MEMBER)

        workspace = cast(Workspace, Workspace.objects.first())
        other_user = User.objects.create_user(username="mohai", password="password")
        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=other_user,
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
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class RemoveUserFromWorkspaceViewtests(AuthAPITestCase):
    def test_remove_user_from_workspace(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": membership.pk},
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_cannot_remove_oneself_from_workspace(self):
        user = self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        membership = WorkspaceMembership.objects.get(
            user=user,
            workspace=workspace,
        )

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": membership.pk},
            )
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        jprint(response.json())

        self.assertIsNotNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_cannot_remove_another_admin_from_workspace(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.ADMIN,
            user=user,
            workspace=workspace,
        )

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": membership.pk},
            )
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        jprint(response.json())

        self.assertIsNotNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_cannot_remove_the_owner_from_workspace(self):
        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        WorkspaceMembership.objects.create(
            role=WorkspaceRole.ADMIN,
            user=user,
            workspace=workspace,
        )

        # Login from second user
        self.client.login(username="mohai", password="password")

        membership = WorkspaceMembership.objects.get(
            role=WorkspaceRole.OWNER,
            workspace=workspace,
        )

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": membership.pk},
            )
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        jprint(response.json())

        self.assertIsNotNone(
            WorkspaceMembership.objects.filter(
                role=WorkspaceRole.OWNER,
                workspace=workspace,
            ).first()
        )

    def test_owner_can_remove_an_admin_from_workspace(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.ADMIN,
            user=user,
            workspace=workspace,
        )

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": membership.pk},
            )
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_regular_member_cannot_remove_anyone_from_workspace(self):
        owner = self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())
        WorkspaceMembership.objects.filter(user=owner).update(role=WorkspaceRole.MEMBER)

        user = User.objects.create_user(username="mohai", password="password")

        membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": membership.pk},
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        self.assertIsNotNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_remove_nonexistent_membership_returns_404(self):
        self.loginUser()

        response = self.client.delete(
            reverse(
                "zane_api:workspace.membership_detail",
                kwargs={"membership_id": 99999},
            )
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class LeaveWorkspaceViewTests(AuthAPITestCase):
    def test_member_can_leave_workspace(self):
        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )
        self.client.login(username="mohai", password="password")

        response = self.client.post(reverse("zane_api:workspace.leave"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_admin_can_leave_workspace(self):
        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.ADMIN,
            user=user,
            workspace=workspace,
        )
        self.client.login(username="mohai", password="password")

        response = self.client.post(reverse("zane_api:workspace.leave"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=workspace,
            ).first()
        )

    def test_owner_cannot_leave_workspace(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        response = self.client.post(reverse("zane_api:workspace.leave"))
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        jprint(response.json())

        self.assertIsNotNone(
            WorkspaceMembership.objects.filter(
                role=WorkspaceRole.OWNER,
                workspace=workspace,
            ).first()
        )

    def test_cannot_leave_workspace_if_not_a_member(self):
        User.objects.create_user(username="mohai", password="password")
        self.client.login(username="mohai", password="password")

        response = self.client.post(reverse("zane_api:workspace.leave"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_leaving_workspace_switches_to_another_workspace_if_member(self):
        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=second_workspace,
        )

        self.client.login(username="mohai", password="password")
        self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": workspace.id},
        )

        response = self.client.post(reverse("zane_api:workspace.leave"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            self.client.session.get(WORKSPACE_SESSION_KEY), second_workspace.id
        )

    def test_leaving_workspace_remove_workspace_session_key_if_no_workspace_left(self):
        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        self.client.login(username="mohai", password="password")
        self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": workspace.id},
        )

        response = self.client.post(reverse("zane_api:workspace.leave"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(self.client.session.get(WORKSPACE_SESSION_KEY))


class TransferWorkspaceOwnershipViewTests(AuthAPITestCase):
    def test_owner_can_transfer_ownership_to_admin(self):
        owner = self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        new_owner = User.objects.create_user(username="mohai", password="password")
        new_owner_membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.ADMIN,
            user=new_owner,
            workspace=workspace,
        )

        response = self.client.post(
            reverse("zane_api:workspace.transfer_ownership"),
            data={"new_owner_id": new_owner_membership.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            WorkspaceMembership.objects.get(user=new_owner, workspace=workspace).role,
            WorkspaceRole.OWNER,
        )
        self.assertEqual(
            WorkspaceMembership.objects.get(user=owner, workspace=workspace).role,
            WorkspaceRole.ADMIN,
        )

    def test_non_owner_cannot_transfer_ownership(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        admin = User.objects.create_user(username="admin_user", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.ADMIN,
            user=admin,
            workspace=workspace,
        )

        other = User.objects.create_user(username="mohai", password="password")
        other_membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=other,
            workspace=workspace,
        )

        self.client.login(username="admin_user", password="password")

        response = self.client.post(
            reverse("zane_api:workspace.transfer_ownership"),
            data={"new_owner_id": other_membership.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_cannot_transfer_ownership_to_non_member(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspace.transfer_ownership"),
            data={"new_owner_id": 99999},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_cannot_transfer_ownership_to_plain_member(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        member = User.objects.create_user(username="mohai", password="password")
        member_membership = WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=member,
            workspace=workspace,
        )

        response = self.client.post(
            reverse("zane_api:workspace.transfer_ownership"),
            data={"new_owner_id": member_membership.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_transfer_ownership_to_self(self):
        owner = self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        owner_membership = WorkspaceMembership.objects.get(
            user=owner,
            workspace=workspace,
        )

        response = self.client.post(
            reverse("zane_api:workspace.transfer_ownership"),
            data={"new_owner_id": owner_membership.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
