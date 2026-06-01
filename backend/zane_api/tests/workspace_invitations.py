from typing import cast

from django.urls import reverse
from rest_framework import status

from ..models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    Project,
    WorkspaceInvitation,
)
from .base import AuthAPITestCase
from ..utils import jprint
from django.utils import timezone
from datetime import timedelta
from django.contrib import auth
from django.contrib.auth.models import User


class WorkspaceInviteUserViewTests(AuthAPITestCase):
    def test_invite_new_user_default(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
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

    def test_cannot_invite_user_who_is_already_in_workspace(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        user = User.objects.create_user(username="mohai", password="another")

        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=workspace,
        )

        data = {
            "username": user.username,
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_invite_oneself(self):
        user = self.loginUser()

        data = {
            "username": user.username,
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

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
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)


class RegenerateWorkspaceInvitationViewTests(AuthAPITestCase):
    def test_regenerate_workspace_invitation_regenerates_token_and_extends_validity(
        self,
    ):
        self.loginUser()

        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        self.assertIsNotNone(new_invitation)

        self.assertAlmostEqual(
            new_invitation.expires_at,
            timezone.now() + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

        data = {"valid_for": 1}
        response = self.client.put(
            reverse(
                "zane_api:workspace.regenerate_invitation",
                kwargs={"id": new_invitation.id},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_invitation = WorkspaceInvitation.objects.get(pk=new_invitation.id)

        self.assertNotEqual(new_invitation.token, updated_invitation.token)
        self.assertNotEqual(new_invitation.expires_at, updated_invitation.expires_at)

        self.assertAlmostEqual(
            updated_invitation.expires_at,
            timezone.now() + timedelta(days=1),
            delta=timedelta(seconds=5),
        )


class WorkspaceRespondToInvitationViewTests(AuthAPITestCase):
    def test_accept_user_invitation_creates_new_user_and_logs_them_in(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Logout current user
        self.client.logout()

        # 3- Accept invitation
        data = {"password": "p4$$word"}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # 4- New user should be created & authenticated
        self.assertEqual(2, User.objects.count())

        new_user = auth.get_user(self.client)
        self.assertTrue(new_user.is_authenticated)
        self.assertEqual("mohai", new_user.username)
        self.assertIsNotNone(User.objects.filter(username=new_user.username).first())

        # 4- Membership should be created for user
        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                user=new_user,
                workspace=workspace,
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, WorkspaceRole.MEMBER)

        # 5- User should be logged into new workspace
        response = self.client.get(
            reverse(
                "zane_api:auth.me",
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        self.assertEqual(data["membership"]["workspace"]["id"], workspace.id)

        # 6- Invitation should be deleted
        self.assertEqual(0, WorkspaceInvitation.objects.count())

    def test_reject_workspace_invitation(self):
        self.loginUser()

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Logout current user
        self.client.logout()

        # 3- Accept invitation
        response = self.client.delete(
            reverse(
                "zane_api:workspace.reject_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(0, WorkspaceInvitation.objects.count())

    def test_cannot_accept_invitation_for_other_user_if_logged_into_different_account(
        self,
    ):
        self.loginUser()

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Accept invitation
        data = {"password": "p4$$word"}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_accept_invitation_for_new_user_validate_password_strength(
        self,
    ):
        self.loginUser()

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Logout current user
        self.client.logout()

        # 3- Accept invitation
        data = {"password": "password"}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "password"))

    def test_accept_user_invitation_from_existing_user_just_create_membership(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        # 0- Create user
        User.objects.create_user(username="mohai", password="password")

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Logout current user
        self.client.logout()

        # 3- Accept invitation
        data = {"password": "password"}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # 4- New user should be created & authenticated
        self.assertEqual(2, User.objects.count())

        new_user = auth.get_user(self.client)
        self.assertTrue(new_user.is_authenticated)
        self.assertEqual("mohai", new_user.username)
        self.assertIsNotNone(User.objects.filter(username=new_user.username).first())

        # 4- Membership should be created for user
        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                user=new_user,
                workspace=workspace,
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, WorkspaceRole.MEMBER)

        # 5- User should be logged into new workspace
        response = self.client.get(
            reverse(
                "zane_api:auth.me",
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        self.assertEqual(data["membership"]["workspace"]["id"], workspace.id)

        # 6- Invitation should be deleted
        self.assertEqual(0, WorkspaceInvitation.objects.count())

    def test_accept_user_invitation_from_existing_user_check_correct_password(self):
        self.loginUser()

        # 0- Create user
        User.objects.create_user(username="mohai", password="p4$$word")

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Logout current user
        self.client.logout()

        # 3- Accept invitation
        data = {"password": "password"}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_accept_user_invitation_with_guest_role_populate_accessible_projects(self):
        self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        # 0- Create project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")

        # 1- Create invitation
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

        # 2- Logout current user
        self.client.logout()

        # 3- Accept invitation
        data = {"password": "p4$$word"}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # 4- New user should be created & authenticated
        self.assertEqual(2, User.objects.count())

        new_user = auth.get_user(self.client)
        self.assertTrue(new_user.is_authenticated)
        self.assertEqual("mohai", new_user.username)
        self.assertIsNotNone(User.objects.filter(username=new_user.username).first())

        # 4- Membership should be created for user
        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                user=new_user,
                workspace=workspace,
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, WorkspaceRole.GUEST)
        self.assertEqual(1, membership.accessible_projects.count())
        self.assertEqual(project, membership.accessible_projects.first())

        # 5- User should be logged into new workspace
        response = self.client.get(
            reverse(
                "zane_api:auth.me",
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        self.assertEqual(data["membership"]["workspace"]["id"], workspace.id)

        # 6- Invitation should be deleted
        self.assertEqual(0, WorkspaceInvitation.objects.count())

    def test_accept_invitation_automatically_when_logged_in(self):
        self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        # 0- Create user
        new_user = User.objects.create_user(username="mohai", password="p4$$word")

        # 1- Create invitation
        data = {
            "username": "mohai",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        new_invitation = cast(WorkspaceInvitation, WorkspaceInvitation.objects.first())

        # 2- Login other user
        self.client.login(username="mohai", password="p4$$word")

        # 3- Accept invitation
        data = {}
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": new_invitation.token},
            ),
            data=data,
        )
        jprint(response.json())
