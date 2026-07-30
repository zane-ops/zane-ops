from django.urls import reverse
from rest_framework import status
from zane_api.models import Workspace, WorkspaceMembership, WorkspaceRole
from zane_api.tests.base import AuthAPITestCase

from ..models import SharedRegistryCredentials


class RegistryCredentialsAdminPermissionsViewTests(AuthAPITestCase):
    """
    Creating, editing and deleting shared registry credentials is Admin —
    editing and deleting moved down from Owner, creating moved up from Member.
    Listing them stays at Member, since services reference them by id.
    """

    def set_role(self, role: WorkspaceRole):
        user = self.loginUser()
        WorkspaceMembership.objects.filter(
            workspace=Workspace.objects.get(memberships__user=user)
        ).update(role=role)

    def test_admin_can_create_registry_credentials(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.post(
            reverse("container_registry:credentials.list"), data={}
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_create_registry_credentials(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.post(
            reverse("container_registry:credentials.list"), data={}
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_can_still_list_registry_credentials(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.get(reverse("container_registry:credentials.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_admin_can_edit_registry_credentials(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.patch(
            reverse(
                "container_registry:credentials.details",
                kwargs={"id": f"{SharedRegistryCredentials.ID_PREFIX}doesnotexist"},
            ),
            data={},
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_edit_registry_credentials(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.patch(
            reverse(
                "container_registry:credentials.details",
                kwargs={"id": f"{SharedRegistryCredentials.ID_PREFIX}doesnotexist"},
            ),
            data={},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_admin_can_delete_registry_credentials(self):
        self.set_role(WorkspaceRole.ADMIN)

        response = self.client.delete(
            reverse(
                "container_registry:credentials.details",
                kwargs={"id": f"{SharedRegistryCredentials.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_cannot_delete_registry_credentials(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.delete(
            reverse(
                "container_registry:credentials.details",
                kwargs={"id": f"{SharedRegistryCredentials.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_member_can_still_view_registry_credentials(self):
        self.set_role(WorkspaceRole.MEMBER)

        response = self.client.get(
            reverse(
                "container_registry:credentials.details",
                kwargs={"id": f"{SharedRegistryCredentials.ID_PREFIX}doesnotexist"},
            )
        )
        self.assertNotEqual(status.HTTP_403_FORBIDDEN, response.status_code)
