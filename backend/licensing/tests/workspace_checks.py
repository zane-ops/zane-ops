import secrets
from typing import List, cast

from django.urls import reverse
from rest_framework import status

from ..models import License, LicenseTiers
from zane_api.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceRole,
)
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from uuid import uuid4
from .fixtures import mock_remote_api_for_licensing
import responses
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class WorkspaceLimitsChecksViewTests(AuthAPITestCase):
    @responses.activate
    def test_cannot_create_more_than_one_workspace_without_installed_license(self):
        self.loginUser()
        self.assertIsNotNone(Workspace.objects.first())

        response = self.client.post(
            reverse("zane_api:workspaces.create"),
            data={"name": "Fredkiss's work"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_cannot_create_more_than_one_workspace_without_valid_license(self):
        self.loginUser()
        self.assertIsNotNone(Workspace.objects.first())

        with mock_remote_api_for_licensing(tier=LicenseTiers.FREE):
            # Install free license
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )

            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)
            self.assertEqual(LicenseTiers.FREE, installed_license.tier)

            # create workspace
            response = self.client.post(
                reverse("zane_api:workspaces.create"),
                data={"name": "Fredkiss's work"},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_should_be_able_to_create_more_than_one_workspace_with_valid_license(self):
        self.loginUser()
        self.assertIsNotNone(Workspace.objects.first())

        with mock_remote_api_for_licensing():
            # Install License
            license_uuid = str(uuid4())
            data = {"uuid": license_uuid}
            response = self.client.post(
                reverse("licensing:license.install"),
                data=data,
            )

            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)

            # Create workspace
            response = self.client.post(
                reverse("zane_api:workspaces.create"),
                data={"name": "Fredkiss's work"},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            self.assertEqual(2, Workspace.objects.count())
            self.assertIsNotNone(
                Workspace.objects.filter(name="Fredkiss's work").first()
            )

    @responses.activate
    def test_cannot_create_more_than_two_invitations_without_installed_license(self):
        user = self.loginUser()

        workspace = cast(Workspace, Workspace.objects.first())

        # Create invitations
        WorkspaceInvitation.objects.bulk_create(
            [
                WorkspaceInvitation(
                    token=secrets.token_hex(16),
                    username="mohai",
                    role=WorkspaceRole.ADMIN,
                    expires_at=timezone.now() + timedelta(days=3),
                    workspace=workspace,
                    invited_by=user,
                ),
                WorkspaceInvitation(
                    token=secrets.token_hex(16),
                    username="ahmedbaset",
                    role=WorkspaceRole.MEMBER,
                    expires_at=timezone.now() + timedelta(days=3),
                    workspace=workspace,
                    invited_by=user,
                ),
            ]
        )

        data = {
            "username": "everx",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_cannot_create_more_than_two_invitations_without_valid_license(self):
        user = self.loginUser()
        workspace = cast(Workspace, Workspace.objects.first())

        # Create invitations -> 3 users in total
        WorkspaceInvitation.objects.bulk_create(
            [
                WorkspaceInvitation(
                    token=secrets.token_hex(16),
                    username="mohai",
                    role=WorkspaceRole.ADMIN,
                    expires_at=timezone.now() + timedelta(days=3),
                    workspace=workspace,
                    invited_by=user,
                ),
                WorkspaceInvitation(
                    token=secrets.token_hex(16),
                    username="ahmedbaset",
                    role=WorkspaceRole.MEMBER,
                    expires_at=timezone.now() + timedelta(days=3),
                    workspace=workspace,
                    invited_by=user,
                ),
            ]
        )

        with mock_remote_api_for_licensing(tier=LicenseTiers.FREE):
            # Install free license
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

            installed_license = cast(License, License.get())
            self.assertIsNotNone(installed_license)
            self.assertEqual(LicenseTiers.FREE, installed_license.tier)

            # Inviting a 3rd user should still be forbidden on the free tier
            data = {
                "username": "everx",
                "role": WorkspaceRole.MEMBER,
            }
            response = self.client.post(
                reverse("zane_api:workspace.invite_user"),
                data=data,
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_user_limit_counts_both_members_and_pending_invitations(self):
        user = self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # 1 member -> 2 users
        member = User.objects.create_user(username="mohai", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=member,
            workspace=workspace,
        )

        # 1 pending invitation -> 3 users
        WorkspaceInvitation.objects.create(
            token=secrets.token_hex(16),
            username="ahmedbaset",
            role=WorkspaceRole.MEMBER,
            expires_at=timezone.now() + timedelta(days=3),
            workspace=workspace,
            invited_by=user,
        )

        # Inviting a 4th user should be forbidden
        data = {
            "username": "everx",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_can_have_up_to_three_users_without_valid_license(self):
        self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # 1 member -> 2 users
        member = User.objects.create_user(username="mohai", password="password")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=member,
            workspace=workspace,
        )

        # Inviting a 3rd user should still be allowed
        data = {
            "username": "ahmedbaset",
            "role": WorkspaceRole.MEMBER,
        }
        response = self.client.post(
            reverse("zane_api:workspace.invite_user"),
            data=data,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

    @responses.activate
    def test_can_have_more_than_three_users_with_valid_license(self):
        self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # Add 2 more members -> 3 users in total
        for username in ["mohai", "ahmedbaset"]:
            user = User.objects.create_user(username=username, password="password")
            WorkspaceMembership.objects.create(
                role=WorkspaceRole.MEMBER,
                user=user,
                workspace=workspace,
            )

        with mock_remote_api_for_licensing():
            # Install valid license
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            self.assertIsNotNone(License.get())

            # Inviting a 4th user should now be allowed
            data = {
                "username": "everx",
                "role": WorkspaceRole.MEMBER,
            }
            response = self.client.post(
                reverse("zane_api:workspace.invite_user"),
                data=data,
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)


class WorkspaceUserLimitOnRegisterViewTests(AuthAPITestCase):
    """
    The user limit must also be enforced when an invitation is *consumed*,
    to close the gap where invitations are created while a license is valid
    but registered after the license is gone
    [TOCTOU](https://en.wikipedia.org/wiki/Time-of-check_to_time-of-use).
    """

    def _create_invitations(
        self,
        workspace: Workspace,
        owner: User,
        usernames: List[str],
    ):
        return WorkspaceInvitation.objects.bulk_create(
            [
                WorkspaceInvitation(
                    token=secrets.token_hex(16),
                    username=username,
                    role=WorkspaceRole.MEMBER,
                    expires_at=timezone.now() + timedelta(days=3),
                    workspace=workspace,
                    invited_by=owner,
                )
                for username in usernames
            ]
        )

    @responses.activate
    def test_can_register_into_workspace_only_up_to_three_users_without_valid_license(
        self,
    ):
        owner = self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # Over-provisioned invitations (created while licensed), license now gone
        invitations = self._create_invitations(
            workspace, owner, ["mohai", "ahmedbaset", "everx"]
        )

        # Registering is still allowed as long as it doesn't exceed 3 real users
        for invitation in invitations[:2]:  # 2 first invitations
            self.client.logout()
            response = self.client.post(
                reverse(
                    "zane_api:workspace.register",
                    kwargs={"token": invitation.token},
                ),
                data={"password": "p4$$word"},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Only 3 users in total created
        self.assertEqual(3, User.objects.count())

        # last invitation (4th user)
        self.client.logout()
        response = self.client.post(
            reverse(
                "zane_api:workspace.register",
                kwargs={"token": invitations[2].token},
            ),
            data={"password": "p4$$word"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        # No new user should have been created
        self.assertEqual(3, User.objects.count())

    @responses.activate
    def test_cannot_register_into_workspace_beyond_three_users_without_valid_license(
        self,
    ):
        owner = self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # 2 existing members -> 3 real users already
        for username in ["mohai", "ahmedbaset"]:
            member = User.objects.create_user(username=username, password="password")
            WorkspaceMembership.objects.create(
                role=WorkspaceRole.MEMBER,
                user=member,
                workspace=workspace,
            )

        # Invitation created while licensed, license now gone
        invitations = self._create_invitations(workspace, owner, ["everx"])

        # Registering a 4th real user should be forbidden
        self.client.logout()
        response = self.client.post(
            reverse(
                "zane_api:workspace.register",
                kwargs={"token": invitations[0].token},
            ),
            data={"password": "p4$$word"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        # No new user should have been created
        self.assertEqual(3, User.objects.count())

    @responses.activate
    def test_can_register_beyond_three_users_with_valid_license(self):
        owner = self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # 2 existing members -> 3 real users already
        for username in ["mohai", "ahmedbaset"]:
            member = User.objects.create_user(username=username, password="password")
            WorkspaceMembership.objects.create(
                role=WorkspaceRole.MEMBER,
                user=member,
                workspace=workspace,
            )

        invitations = self._create_invitations(workspace, owner, ["everx"])

        with mock_remote_api_for_licensing():
            # Install valid license
            response = self.client.post(
                reverse("licensing:license.install"),
                data={"uuid": str(uuid4())},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            self.assertIsNotNone(License.get())

            # Registering a 4th real user should now be allowed
            self.client.logout()
            response = self.client.post(
                reverse(
                    "zane_api:workspace.register",
                    kwargs={"token": invitations[0].token},
                ),
                data={"password": "p4$$word"},
            )
            jprint(response.json())
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            self.assertEqual(4, User.objects.count())

    @responses.activate
    def test_accepting_invitation_for_existing_user_is_allowed_beyond_limit(self):
        """
        Accepting an invitation for an *existing* account does not create a new
        user, so it must not be blocked even when the instance is over the limit.
        """
        owner = self.loginUser()  # 1st user (owner)
        workspace = cast(Workspace, Workspace.objects.first())

        # Existing members -> already over the limit (4 users), no license installed
        for username in ["ahmedbaset", "everx"]:
            member = User.objects.create_user(username=username, password="password")
            WorkspaceMembership.objects.create(
                role=WorkspaceRole.MEMBER,
                user=member,
                workspace=workspace,
            )

        # `mohai` already has an account but is not yet a member of the workspace
        User.objects.create_user(username="mohai", password="password")

        invitation = WorkspaceInvitation.objects.create(
            token=secrets.token_hex(16),
            username="mohai",
            role=WorkspaceRole.MEMBER,
            expires_at=timezone.now() + timedelta(days=3),
            workspace=workspace,
            invited_by=owner,
        )

        self.client.login(username="mohai", password="password")
        response = self.client.post(
            reverse(
                "zane_api:workspace.accept_invitation",
                kwargs={"token": invitation.token},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
