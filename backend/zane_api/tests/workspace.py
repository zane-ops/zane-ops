from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from ..models import (
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
from .base import AuthAPITestCase, APITestCase
from ..utils import jprint
from ..constants import WORKSPACE_SESSION_KEY


class WorkspaceProjectCreateViewTests(AuthAPITestCase):
    def test_create_project_should_be_done_in_current_workspace(self):
        owner = self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())

        p = Project.objects.get(slug="zane-ops")

        workspace = Workspace.objects.get(memberships__user=owner)
        self.assertEqual(workspace, p.workspace)

    def test_cannot_create_project_if_not_admin(self):
        owner = self.loginUser()
        WorkspaceMembership.objects.filter(user=owner).update(role=WorkspaceRole.MEMBER)

        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertEqual(0, Project.objects.count())


class WorkspaceProjectListViewTests(AuthAPITestCase):
    def test_list_projects_show_projects_in_current_workspace(self):
        owner = self.loginUser()

        first_workspace = Workspace.objects.get(memberships__user=owner)

        second_workspace = Workspace.objects.create(name="Second workspace")

        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", workspace=first_workspace),
                Project(slug="gh-next", workspace=first_workspace),
                Project(slug="zaneops", workspace=first_workspace),
                Project(slug="stop", workspace=second_workspace),
            ]
        )

        response = self.client.get(reverse("zane_api:projects.list"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json()
        self.assertEqual(3, len(project_list))

    def test_can_list_projects_even_if_just_a_guest(self):
        owner = self.loginUser()
        WorkspaceMembership.objects.filter(user=owner).update(role=WorkspaceRole.GUEST)

        workspace = Workspace.objects.get(memberships__user=owner)

        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", workspace=workspace),
                Project(slug="gh-next", workspace=workspace),
                Project(slug="zaneops", workspace=workspace),
            ]
        )

        response = self.client.get(reverse("zane_api:projects.list"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json()
        self.assertEqual(0, len(project_list))

    def test_can_only_list_accessible_projects_if_guest(self):
        owner = self.loginUser()

        workspace = Workspace.objects.get(memberships__user=owner)

        projects = Project.objects.bulk_create(
            [
                Project(slug="gh-clone", workspace=workspace),
                Project(slug="gh-next", workspace=workspace),
                Project(slug="zaneops", workspace=workspace),
                Project(slug="locaci", workspace=workspace),
            ]
        )
        membership = WorkspaceMembership.objects.get(user=owner)
        membership.role = WorkspaceRole.GUEST
        membership.save()
        membership.accessible_projects.add(*projects[:2])

        response = self.client.get(reverse("zane_api:projects.list"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json()
        self.assertEqual(2, len(project_list))


class WorkspaceProjectDetailViewTests(AuthAPITestCase):
    def test_project_member_can_see_all_workspace_projects(self):
        owner = self.loginUser()

        first_workspace = Workspace.objects.get(memberships__user=owner)
        WorkspaceMembership.objects.filter(user=owner).update(role=WorkspaceRole.MEMBER)

        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", workspace=first_workspace),
            ]
        )

        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_project_guest_can_only_see_accessible_projects(self):
        owner = self.loginUser()

        workspace = Workspace.objects.get(memberships__user=owner)

        projects = Project.objects.bulk_create(
            [
                Project(slug="gh-next", workspace=workspace),
                Project(slug="zaneops", workspace=workspace),
            ]
        )
        membership = WorkspaceMembership.objects.get(user=owner)
        membership.role = WorkspaceRole.GUEST
        membership.save()
        membership.accessible_projects.add(projects[0])

        response = self.client.get(
            reverse(
                "zane_api:projects.details",
                kwargs=dict(slug="zaneops"),
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:projects.details",
                kwargs=dict(slug="gh-next"),
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class OnBoardingTests(APITestCase):
    def test_create_initial_user_creates_default_workspace_without_providing_workspace_name(
        self,
    ):
        response = self.client.post(
            reverse("zane_api:auth.create_initial_user"),
            data={
                "username": "mohai",
                "password": "mohai123",
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        default_user = cast(User, User.objects.filter(username="mohai").first())
        self.assertIsNotNone(default_user)

        default_workspace = cast(Workspace, Workspace.objects.first())
        self.assertIsNotNone(default_workspace)

        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                workspace=default_workspace, user=default_user
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(WorkspaceRole.OWNER, membership.role)

    def test_create_initial_user_with_custom_workspace_name(self):
        response = self.client.post(
            reverse("zane_api:auth.create_initial_user"),
            data={
                "username": "mohai",
                "password": "mohai123",
                "workspace_name": "Custom workspace",
            },
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        default_user = cast(User, User.objects.filter(username="mohai").first())
        self.assertIsNotNone(default_user)

        default_workspace = cast(
            Workspace, Workspace.objects.filter(name="Custom workspace").first()
        )
        self.assertIsNotNone(default_workspace)

        membership = cast(
            WorkspaceMembership,
            WorkspaceMembership.objects.filter(
                workspace=default_workspace, user=default_user
            ).first(),
        )
        self.assertIsNotNone(membership)
        self.assertEqual(WorkspaceRole.OWNER, membership.role)


class WorkspaceMiddlewareTests(AuthAPITestCase):
    def test_set_workspace_when_login(self):
        response = self.client.post(
            reverse("zane_api:auth.login"),
            data={"username": "Fredkiss3", "password": "password"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # Verify that workspace session is set
        self.assertIsNotNone(self.client.session.get(WORKSPACE_SESSION_KEY))

        # auth.me exposes the workspace; use it to verify which one is active
        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        workspace = Workspace.objects.filter(
            memberships__user__username="Fredkiss3"
        ).get()

        self.assertEqual(response.json()["membership"]["workspace"]["id"], workspace.id)

    def test_request_workspace_falls_back_to_first_membership_without_session_key(self):
        user = self.loginUser()  # manual login doesn't set the workspace in the session

        self.assertIsNone(self.client.session.get(WORKSPACE_SESSION_KEY))

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(user=user, workspace=second_workspace)

        first_workspace = Workspace.objects.filter(memberships__user=user).earliest(
            "created_at"
        )

        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            response.json()["membership"]["workspace"]["id"], first_workspace.id
        )


class EditWorkspaceTests(AuthAPITestCase):
    def test_can_edit_workspace_if_owner(self):
        self.loginUser()

        response = self.client.put(
            reverse("zane_api:workspace.details"),
            data={"name": "Fredkiss corp"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_cannot_edit_workspace_if_not_owner(self):
        user = self.loginUser()
        WorkspaceMembership.objects.filter(user=user).update(role=WorkspaceRole.MEMBER)

        response = self.client.put(
            reverse("zane_api:workspace.details"),
            data={"name": "Fredkiss corp"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class CreateWorkspaceTests(AuthAPITestCase):
    def test_create_workspace_successful(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspaces.create"),
            data={"name": "Fredkiss's work"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

    def test_cannot_create_workspace_if_not_instance_admin(self):
        user = self.loginUser()
        user.is_superuser = False
        user.save()

        response = self.client.post(
            reverse("zane_api:workspaces.create"),
            data={"name": "Fredkiss's work"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class SwitchWorkspaceViewTests(AuthAPITestCase):
    def test_switch_workspace_sets_session_key(self):
        user = self.loginUser()

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            user=user, workspace=second_workspace, role=WorkspaceRole.ADMIN
        )

        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": second_workspace.id},
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(
            self.client.session.get(WORKSPACE_SESSION_KEY), second_workspace.id
        )

        # auth.me exposes the workspace; use it to verify which one is active
        response = self.client.get(reverse("zane_api:auth.me"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            response.json()["membership"]["workspace"]["id"], second_workspace.id
        )

    def test_cannot_switch_to_a_workspace_without_being_a_member(self):
        self.loginUser()

        other_workspace = Workspace.objects.create(name="Other workspace")

        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": other_workspace.id},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_switch_workspace_nonexistent(self):
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": "wrk_doesnotexist"},
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_switch_workspace_unauthenticated(self):
        workspace = cast(Workspace, Workspace.objects.first())
        response = self.client.post(
            reverse("zane_api:workspaces.switch"),
            data={"workspace_id": workspace.id},
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)


class DeleteWorkspaceViewTests(AuthAPITestCase):
    def test_delete_workspace_deletes_projects_and_services(self):
        user = self.loginUser()
        first_workspace = cast(Workspace, Workspace.objects.first())

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=second_workspace,
        )

        self.create_and_deploy_caddy_docker_service()
        self.create_and_deploy_git_service()

        response = self.client.delete(reverse("zane_api:workspace.details"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertIsNone(Workspace.objects.filter(pk=first_workspace.id).first())
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(Service.objects.count(), 0)

    def test_delete_workspace_update_workspace_session_key(self):
        user = self.loginUser()

        first_workspace = cast(Workspace, Workspace.objects.first())

        second_workspace = Workspace.objects.create(name="Second workspace")
        WorkspaceMembership.objects.create(
            role=WorkspaceRole.MEMBER,
            user=user,
            workspace=second_workspace,
        )
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())

        response = self.client.delete(reverse("zane_api:workspace.details"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertNotEqual(
            self.client.session.get(WORKSPACE_SESSION_KEY), first_workspace.id
        )
        self.assertEqual(
            self.client.session.get(WORKSPACE_SESSION_KEY), second_workspace.id
        )

    async def test_delete_workspace_deletes_projects_resources(self):
        await self.aLoginUser()

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
                    new_value={
                        "key": "USER_UID",
                        "value": "1000",
                    },
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "USER_GID",
                        "value": "1000",
                    },
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

        response = await self.async_client.delete(reverse("zane_api:workspace.details"))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Service are deleted
        self.assertEqual(
            0,
            await Service.objects.filter(
                slug__in=[service1.slug, service2.slug]
            ).acount(),
        )

        # Deployments are cleaned up
        self.assertEqual(
            0,
            await Deployment.objects.filter(
                service__slug__in=[service1.slug, service2.slug]
            ).acount(),
        )

        archived_service = cast(
            ArchivedDockerService,
            await (
                ArchivedDockerService.objects.filter(original_id=service1.id)
                .prefetch_related("volumes")
                .prefetch_related("env_variables")
                .prefetch_related("ports")
                .prefetch_related("urls")
            ).afirst(),
        )
        self.assertIsNotNone(archived_service)

        # Volumes are cleaned up
        deleted_volume = await Volume.objects.filter(name="gitea").afirst()
        self.assertIsNone(deleted_volume)
        self.assertEqual(1, await archived_service.volumes.acount())

        # Configs are cleaned up
        deleted_config = await Config.objects.filter(name="caddyfile").afirst()
        self.assertIsNone(deleted_config)
        self.assertEqual(1, await archived_service.configs.acount())

        # env variables are cleaned up
        deleted_envs = EnvVariable.objects.filter(service__slug=service1.slug)
        self.assertEqual(0, await deleted_envs.acount())
        self.assertEqual(2, await archived_service.env_variables.acount())

        # ports are cleaned up
        deleted_ports = PortConfiguration.objects.filter(service__slug=service1.slug)
        self.assertEqual(0, await deleted_ports.acount())
        self.assertEqual(1, await archived_service.ports.acount())

        # urls are cleaned up
        deleted_urls = URL.objects.filter(domain="gitea.zane.local", base_path="/")
        self.assertEqual(0, await deleted_urls.acount())
        self.assertEqual(2, await archived_service.urls.acount())

        # healthcheck are cleaned up
        deleted_healthcheck = await HealthCheck.objects.filter().afirst()
        self.assertIsNone(deleted_healthcheck)

        archived_service = await ArchivedGitService.objects.filter(
            original_id=service2.id
        ).afirst()
        self.assertIsNotNone(archived_service)

        # --- Docker Resources ---
        # service is removed
        self.assertEqual(
            0,
            len(
                self.fake_docker_client.services_list(
                    filters={"label": ["zane-managed=true"]}
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                self.fake_docker_client.images_list(
                    filters={"label": ["zane-managed=true"]}
                )
            ),
        )

        # volumes are unmounted
        self.assertEqual(0, len(self.fake_docker_client.volume_map))
