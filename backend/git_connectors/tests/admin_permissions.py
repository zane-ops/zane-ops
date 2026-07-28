from django.urls import reverse
from rest_framework import status
from zane_api.models import GitApp, Workspace, WorkspaceMembership, WorkspaceRole
from zane_api.tests.base import AuthAPITestCase

from ..models import GitHubApp, GitlabApp


class ConnectorAdminPermissionsViewTests(AuthAPITestCase):
    """
    Git connectors moved from Owner to Admin: on a small team, Owner-only meant
    either pinging the Owner weekly or sharing the Owner login.

    These only assert the role boundary, so the granted case asserts "not 403"
    — the request still fails later on a missing app or missing params.
    """

    def set_role(self, role: WorkspaceRole):
        user = self.loginUser()
        WorkspaceMembership.objects.filter(
            workspace=Workspace.objects.get(memberships__user=user)
        ).update(role=role)

    def test_admin_can_setup_github_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.get(reverse("git_connectors:github.setup"))
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_setup_github_app(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.get(reverse("git_connectors:github.setup"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_edit_github_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.patch(
            reverse(
                "git_connectors:github.details",
                kwargs={"id": f"{GitHubApp.ID_PREFIX}doesnotexist"},
            ),
            data={},
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_edit_github_app(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.patch(
            reverse(
                "git_connectors:github.details",
                kwargs={"id": f"{GitHubApp.ID_PREFIX}doesnotexist"},
            ),
            data={},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_test_github_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.get(
            reverse(
                "git_connectors:github.test",
                kwargs={"id": f"{GitHubApp.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_create_gitlab_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.post(reverse("git_connectors:gitlab.create"), data={})
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_create_gitlab_app(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.post(reverse("git_connectors:gitlab.create"), data={})
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_setup_gitlab_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.get(reverse("git_connectors:gitlab.setup"))
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_update_gitlab_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.put(
            reverse(
                "git_connectors:gitlab.update",
                kwargs={"id": f"{GitlabApp.ID_PREFIX}doesnotexist"},
            ),
            data={},
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_update_gitlab_app(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.put(
            reverse(
                "git_connectors:gitlab.update",
                kwargs={"id": f"{GitlabApp.ID_PREFIX}doesnotexist"},
            ),
            data={},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_sync_gitlab_repositories(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.put(
            reverse(
                "git_connectors:gitlab.sync_repositories",
                kwargs={"id": f"{GitlabApp.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_test_gitlab_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.get(
            reverse(
                "git_connectors:gitlab.test",
                kwargs={"id": f"{GitlabApp.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_delete_git_app(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.delete(
            reverse(
                "git_connectors:git_apps.details",
                kwargs={"id": f"{GitApp.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_delete_git_app(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.delete(
            reverse(
                "git_connectors:git_apps.details",
                kwargs={"id": f"{GitApp.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_can_still_view_git_app_details(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.get(
            reverse(
                "git_connectors:git_apps.details",
                kwargs={"id": f"{GitApp.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)
