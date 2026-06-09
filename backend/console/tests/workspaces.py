from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from zane_api.models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    Project,
    Service,
    DeploymentChange,
    Deployment,
    PortConfiguration,
    EnvVariable,
    ArchivedDockerService,
    Config,
    HealthCheck,
    ArchivedGitService,
    URL,
    Volume,
)
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

    def test_can_transfer_ownership_to_non_member(self):
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
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                user=non_member, workspace=workspace, role=WorkspaceRole.OWNER
            ).exists()
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                user=user, workspace=workspace, role=WorkspaceRole.OWNER
            ).exists()
        )

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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "owner_id"))

    def test_cannot_transfer_ownership_to_suspended_user(self):
        self.loginUser()

        user = User.objects.create_user(username="mohai", password="password")
        workspace = Workspace.objects.create(name="mohai workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceRole.OWNER
        )
        suspended_user = User.objects.create_user(
            username="suspended", password="password", is_active=False
        )
        WorkspaceMembership.objects.create(
            user=suspended_user, workspace=workspace, role=WorkspaceRole.MEMBER
        )

        response = self.client.put(
            reverse(
                "console:workspace.transfer_ownership", kwargs={"id": workspace.pk}
            ),
            data={"owner_id": suspended_user.pk},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


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
        project, _ = self.create_and_deploy_caddy_docker_service()
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

    async def test_delete_workspace_cleans_up_all_resources(self):
        await self.aLoginUser()

        workspace = await Workspace.objects.acreate(name="mohai workspace")

        project, service1 = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "name": "caddy-data",
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "echo 1",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "name": "caddyfile",
                        "mount_path": "/etc/caddy/Caddyfile",
                        "contents": "respond hello",
                        "language": "plaintext",
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"key": "USER_UID", "value": "1000"},
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"key": "USER_GID", "value": "1000"},
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "gitea.zane.local",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 80,
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={"host": 8080, "forwarded": 80},
                ),
            ],
        )
        project, service2 = await self.acreate_and_deploy_git_service()

        response = await self.async_client.delete(
            reverse("console:workspace.detail", kwargs={"id": workspace.pk})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(
            0,
            await Service.objects.filter(
                slug__in=[service1.slug, service2.slug]
            ).acount(),
        )
        self.assertEqual(
            0,
            await Deployment.objects.filter(
                service__slug__in=[service1.slug, service2.slug]
            ).acount(),
        )

        archived_service = cast(
            ArchivedDockerService,
            await ArchivedDockerService.objects.filter(original_id=service1.id)
            .prefetch_related("volumes", "env_variables", "ports", "urls", "configs")
            .afirst(),
        )
        self.assertIsNotNone(archived_service)

        self.assertIsNone(await Volume.objects.filter(name="caddy-data").afirst())
        self.assertEqual(1, await archived_service.volumes.acount())

        self.assertIsNone(await Config.objects.filter(name="caddyfile").afirst())
        self.assertEqual(1, await archived_service.configs.acount())

        self.assertEqual(
            0, await EnvVariable.objects.filter(service__slug=service1.slug).acount()
        )
        self.assertEqual(2, await archived_service.env_variables.acount())

        self.assertEqual(
            0,
            await PortConfiguration.objects.filter(
                service__slug=service1.slug
            ).acount(),
        )
        self.assertEqual(1, await archived_service.ports.acount())

        self.assertEqual(
            0,
            await URL.objects.filter(domain="gitea.zane.local", base_path="/").acount(),
        )
        self.assertEqual(2, await archived_service.urls.acount())

        self.assertIsNone(await HealthCheck.objects.filter().afirst())

        self.assertIsNotNone(
            await ArchivedGitService.objects.filter(original_id=service2.id).afirst()
        )

        self.assertEqual(
            0,
            len(
                self.fake_docker_client.services_list(
                    filters={"label": ["zane-managed=true"]}
                )
            ),
        )
        self.assertEqual(0, len(self.fake_docker_client.volume_map))
