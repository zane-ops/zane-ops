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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

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
        jprint(response.json())
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
        jprint(response.json())
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
        jprint(response.json())
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
        jprint(response.json())
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
        jprint(response.json())
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
        jprint(response.json())
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
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


EMPTY_SET = frozenset()


class ViewerComposeStackSecretFieldsViewTests(ViewerComposeStackTestBase):
    """
    `deploy_token` is enough to deploy through the `AllowAny` webhook routes, so
    a Viewer reading it off the stack details payload would have write access.
    The compose contents, env overrides and configs are secrets in the same
    payload, and the change records carry the same values in their
    `old_value`/`new_value`.
    """

    # The tests below assert on these sets against `payload.keys()`, which is
    # itself a set-like view, using set algebra (union, intersection, difference, etc.):
    #
    #   FIELDS & payload.keys()  -> intersection: Are there secrets fields included in the response for a viewer ?
    #                               Should be empty for a viewer, since any field in common means the field wasn't stripped.
    #
    #   FIELDS - payload.keys()  -> difference: Is there any field missing in the response for a member ?
    #                               Should be empty for a member, since any element missing means the field was wrongly stripped.
    #
    # Both are asserted equal to the empty set rather than tested per element,
    # so a failure reports every offending field at once.
    STACK_MEMBER_ONLY_FIELDS = frozenset(
        [
            "deploy_token",
            "user_content",
            "computed_content",
            "env_overrides",
            "configs",
            "unapplied_changes",
        ]
    )
    # the snapshot never carries `deploy_token` nor `unapplied_changes`
    SNAPSHOT_MEMBER_ONLY_FIELDS = frozenset(
        [
            "user_content",
            "computed_content",
            "env_overrides",
            "configs",
        ]
    )
    DEPLOYMENT_MEMBER_ONLY_FIELDS = frozenset(["changes"])

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
        data = response.json()
        jprint(data)
        missing_fields = self.STACK_MEMBER_ONLY_FIELDS - data.keys()
        self.assertEqual(EMPTY_SET, missing_fields)

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
        data = response.json()
        jprint(data)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        non_stripped_fields = self.STACK_MEMBER_ONLY_FIELDS & data.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

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
        data = response.json()
        jprint(data)

        for stack in data:
            non_stripped_fields = self.STACK_MEMBER_ONLY_FIELDS & stack.keys()
            self.assertEqual(EMPTY_SET, non_stripped_fields)

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
        non_stripped_fields = self.SNAPSHOT_MEMBER_ONLY_FIELDS & snapshot.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

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
        data = response.json()
        jprint(data)

        # Check that secret fields from deployment are included
        missing_fields = self.DEPLOYMENT_MEMBER_ONLY_FIELDS - data.keys()
        self.assertEqual(EMPTY_SET, missing_fields)

        # Also check that secret fields from snapshot are included
        missing_fields = (
            self.SNAPSHOT_MEMBER_ONLY_FIELDS - data["stack_snapshot"].keys()
        )
        self.assertEqual(EMPTY_SET, missing_fields)

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

        # Check that deployment does not contain secret fields
        non_stripped_fields = self.DEPLOYMENT_MEMBER_ONLY_FIELDS & data.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

        # Check that snapshots also do not contain secret fields
        snapshot = data["stack_snapshot"]
        non_stripped_fields = self.SNAPSHOT_MEMBER_ONLY_FIELDS & snapshot.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

    def test_viewer_does_not_see_secret_fields_in_deployment_list(self):
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
        data = response.json()
        jprint(data)

        for deployment in data["results"]:
            # Check that deployment does not contain secret fields
            non_stripped_fields = self.DEPLOYMENT_MEMBER_ONLY_FIELDS & deployment.keys()
            self.assertEqual(EMPTY_SET, non_stripped_fields)
            # Check that snapshots also do not contain secret fields
            snapshot = deployment["stack_snapshot"]
            non_stripped_fields = self.SNAPSHOT_MEMBER_ONLY_FIELDS & snapshot.keys()
            self.assertEqual(EMPTY_SET, non_stripped_fields)

    def test_deployment_snapshot_stored_in_db_keeps_secret_fields(self):
        """
        The stripping must happen at serialization time only — the snapshot
        persisted on the deployment still needs every field for redeploys.
        """
        _, stack = self.create_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE, slug="my-stack"
        )
        deployment = ComposeStackDeployment.objects.create(stack=stack)
        stack.apply_pending_changes(deployment=deployment)
        deployment.stack_snapshot = stack.snapshot.to_dict()  # type: ignore
        deployment.save()

        missing_fields = (
            self.SNAPSHOT_MEMBER_ONLY_FIELDS - deployment.stack_snapshot.keys()  # type: ignore
        )
        self.assertEqual(EMPTY_SET, missing_fields)
