from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from zane_api.models import Workspace, WorkspaceMembership, WorkspaceRole, Project, Service
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint


class TransferWorkspaceOwnershipViewTests(AuthAPITestCase):
    def test_instance_owner_can_transfer_workspace_ownership(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")
        workspace = Workspace.objects.create(name="mohai workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceRole.OWNER
        )
        new_owner = User.objects.create_user(username="newowner", password="password")
        WorkspaceMembership.objects.create(
            user=new_owner, workspace=workspace, role=WorkspaceRole.MEMBER
        )

        response = self.client.put(
            reverse(
                "console:workspace.transfer_ownership", kwargs={"id": workspace.pk}
            ),
            data={"owner_id": new_owner.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                user=new_owner, workspace=workspace, role=WorkspaceRole.OWNER
            ).exists()
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                user=user, workspace=workspace, role=WorkspaceRole.OWNER
            ).exists()
        )

    def test_cannot_transfer_ownership_to_non_member(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")
        workspace = Workspace.objects.create(name="mohai workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceRole.OWNER
        )
        non_member = User.objects.create_user(username="stranger", password="password")

        response = self.client.put(
            reverse(
                "console:workspace.transfer_ownership", kwargs={"id": workspace.pk}
            ),
            data={"owner_id": non_member.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_non_instance_owner_cannot_transfer_workspace_ownership(self):
        user = User.objects.create_user(username="mohai", password="password")
        workspace = Workspace.objects.create(name="mohai workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceRole.OWNER
        )
        self.client.login(username="mohai", password="password")

        response = self.client.put(
            reverse(
                "console:workspace.transfer_ownership", kwargs={"id": workspace.pk}
            ),
            data={"owner_id": user.pk},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_transfer_ownership_for_nonexistent_workspace(self):
        self.loginUser()

        response = self.client.put(
            reverse(
                "console:workspace.transfer_ownership",
                kwargs={"id": "nonexistent"},
            ),
            data={"owner_id": 1},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_transfer_ownership_to_nonexistent_user(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")
        workspace = Workspace.objects.create(name="mohai workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceRole.OWNER
        )

        response = self.client.put(
            reverse(
                "console:workspace.transfer_ownership", kwargs={"id": workspace.pk}
            ),
            data={"owner_id": 99999},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class DeleteWorkspaceViewTests(AuthAPITestCase):
    def test_instance_owner_can_delete_workspace(self):
        self.loginUser()

        workspace = Workspace.objects.create(name="mohai workspace")

        response = self.client.delete(
            reverse("console:workspace.detail", kwargs={"id": workspace.pk})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertFalse(Workspace.objects.filter(pk=workspace.pk).exists())

    def test_deleting_workspace_also_deletes_its_projects_and_services(self):
        self.loginUser()

        workspace = Workspace.objects.create(name="mohai workspace")
        project = Project.objects.create(slug="my-project", workspace=workspace)
        Service.objects.create(slug="my-service", project=project)

        response = self.client.delete(
            reverse("console:workspace.detail", kwargs={"id": workspace.pk})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(0, Project.objects.filter(workspace=workspace).count())
        self.assertEqual(0, Service.objects.filter(project=project).count())

    def test_non_instance_owner_cannot_delete_workspace(self):
        user = User.objects.create_user(username="mohai", password="password")
        workspace = Workspace.objects.create(name="mohai workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceRole.OWNER
        )
        self.client.login(username="mohai", password="password")

        response = self.client.delete(
            reverse("console:workspace.detail", kwargs={"id": workspace.pk})
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertTrue(Workspace.objects.filter(pk=workspace.pk).exists())

    def test_delete_nonexistent_workspace(self):
        self.loginUser()

        response = self.client.delete(
            reverse("console:workspace.detail", kwargs={"id": "nonexistent"})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
