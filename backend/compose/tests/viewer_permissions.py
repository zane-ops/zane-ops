from django.urls import reverse
from rest_framework import status
from zane_api.models import Environment, WorkspaceMembership, WorkspaceRole
from zane_api.utils import jprint

from ..models import ComposeStackDeployment
from .fixtures import DOCKER_COMPOSE_WEB_SERVICE
from .stacks import ComposeStackAPITestBase


class ViewerComposeStackTestBase(ComposeStackAPITestBase):
    """
    Per `backend/notes/PERMISSIONS_CHANGELIST.md`, a Viewer sees a stack's
    name, public URLs and up-down status — never its compose file, env
    overrides, configs or deploy token.
    """

    def setup_viewer_with_stack(self, slug: str = "my-stack"):
        project, stack = self.create_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE, slug=slug
        )
        deployment = ComposeStackDeployment.objects.create(stack=stack)
        stack.apply_pending_changes(deployment=deployment)
        deployment.stack_snapshot = stack.snapshot.to_dict()  # type: ignore
        deployment.save()

        # Demote user to viewer
        membership = WorkspaceMembership.objects.get(workspace=project.workspace)
        membership.role = WorkspaceRole.VIEWER
        membership.save()
        membership.accessible_projects.add(project)

        return project, stack, deployment


class ViewerComposeStackGrantedViewTests(ViewerComposeStackTestBase):
    def test_viewer_can_list_stacks(self):
        project, _, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

    def test_viewer_can_view_stack_details(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_list_stack_deployments(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.deployments.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_view_stack_deployment_details(self):
        project, stack, deployment = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.deployments.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_view_stack_metrics(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.metrics",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class ViewerComposeStackDeniedViewTests(ViewerComposeStackTestBase):
    def test_viewer_cannot_view_stack_runtime_logs(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stack.runtime_logs",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_stack_build_logs(self):
        project, stack, deployment = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stack.deployments.build_logs",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_deploy_stack(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_update_stack(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.put(
            reverse(
                "compose:stacks.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"slug": "renamed"},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_regenerate_stack_deploy_token(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.put(
            reverse(
                "compose:stacks.regenerate_deploy_token",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class ViewerComposeStackSecretFieldsViewTests(ViewerComposeStackTestBase):
    MEMBER_ONLY_FIELDS = [
        "deploy_token",
        "user_content",
        "computed_content",
        "env_overrides",
        "configs",
        "unapplied_changes",
    ]
    DEPLOYMENT_MEMBER_ONLY_FIELDS = [
        "changes",
    ]

    def test_member_sees_secret_fields_in_stack_details(self):
        project, stack = self.create_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE, slug="my-stack"
        )
        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        response = self.client.get(
            reverse(
                "compose:stacks.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        for field in self.MEMBER_ONLY_FIELDS:
            self.assertIn(field, response.json())

    def test_viewer_does_not_see_secret_fields_in_stack_details(self):
        project, stack, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        jprint(data)
        for field in self.MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, data)

    def test_viewer_does_not_see_secret_fields_in_stack_list(self):
        project, _, _ = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        for field in self.MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, response.json()[0])

    def test_viewer_does_not_see_secret_fields_in_deployment_snapshot(self):
        project, stack, deployment = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.deployments.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        snapshot = response.json()["stack_snapshot"]
        jprint(snapshot)
        for field in self.MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, snapshot)

    def test_member_sees_changes_in_stack_deployment(self):
        project, stack = self.create_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE, slug="my-stack"
        )
        deployment = ComposeStackDeployment.objects.create(stack=stack)
        stack.apply_pending_changes(deployment=deployment)
        deployment.stack_snapshot = stack.snapshot.to_dict()  # type: ignore
        deployment.save()

        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        response = self.client.get(
            reverse(
                "compose:stacks.deployments.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        for field in self.DEPLOYMENT_MEMBER_ONLY_FIELDS:
            self.assertIn(field, response.json())

    def test_viewer_does_not_see_changes_in_stack_deployment(self):
        """
        `changes` records carry the compose content and env overrides in their
        `old_value` / `new_value`.
        """
        project, stack, deployment = self.setup_viewer_with_stack()

        response = self.client.get(
            reverse(
                "compose:stacks.deployments.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                    "hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        jprint(data)
        for field in self.DEPLOYMENT_MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, data)
