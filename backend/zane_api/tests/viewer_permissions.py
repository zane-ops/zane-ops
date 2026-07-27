from django.urls import reverse
from rest_framework import status

from ..models import (
    Environment,
    WorkspaceMembership,
    WorkspaceRole,
)
from ..utils import jprint
from .base import AuthAPITestCase
from uuid import uuid4


class ViewerEndpointsTestBase(AuthAPITestCase):
    """
    The Viewer surface, as drafted in `notes/PERMISSIONS_CHANGELIST.md`:

    - apps / services / stacks: name, public URLs, up-down status
    - deployments: list, detail, status, history
    - metrics
    - workspace: view details, switch, leave

    Explicitly **not**: logs of any kind, env variables, deploy tokens,
    terminal, member list, detected ports.
    """

    def setup_viewer_with_service(self, slug: str = "redis"):
        project, service = self.create_redis_docker_service(slug=slug)
        deployment = service.prepare_new_docker_deployment()

        # Demote user to viewer
        membership = WorkspaceMembership.objects.get(workspace=project.workspace)
        membership.role = WorkspaceRole.VIEWER
        membership.save()
        membership.accessible_projects.add(project)

        return project, service, deployment


class ViewerGrantedEndpointsViewTests(ViewerEndpointsTestBase):
    def test_viewer_can_view_service_details(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_list_services(self):
        project, _, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={
                    "slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

    def test_viewer_can_list_service_deployments(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

    def test_viewer_can_view_single_deployment(self):
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment_single",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_list_recent_deployments(self):
        self.setup_viewer_with_service()

        response = self.client.get(reverse("zane_api:deployments.recent"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_view_service_metrics(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.metrics",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_view_deployment_metrics(self):
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment_metrics",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_viewer_can_search_resources(self):
        self.setup_viewer_with_service()

        response = self.client.get(
            reverse("zane_api:resources.search"), QUERY_STRING="query=redis"
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class ViewerDeniedEndpointsViewTests(ViewerEndpointsTestBase):
    def test_viewer_cannot_view_runtime_logs(self):
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment.runtime_logs",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_runtime_logs_with_context(self):
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment.runtime_logs.with_context",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                    "time": "1767225600",
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_build_logs(self):
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment.build_logs",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_http_logs_endpoint(self):
        self.setup_viewer_with_service()

        response = self.client.get(reverse("zane_api:http_logs"))
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_http_logs_fields(self):
        _, service, __ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse("zane_api:http_logs.fields"),
            QUERY_STRING=f"field=request_ip&value=127&service_id={service.id}",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_single_http_logs(self):
        _, service, __ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse("zane_api:http_logs.single", kwargs={"request_uuid": str(uuid4())}),
            QUERY_STRING=f"field=request_ip&value=127&service_id={service.id}",
        )
        jprint(response.json())

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_detected_ports(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.detected_ports",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_list_workspace_members(self):
        self.setup_viewer_with_service()

        response = self.client.get(reverse("zane_api:workspace.list_members"))
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_view_environment_details(self):
        project, _, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_list_shared_env_variables(self):
        project, _, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:environment.variables-list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_deploy_service(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            ),
            data={},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_request_service_changes(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            ),
            data={},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_viewer_cannot_regenerate_deploy_token(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.patch(
            reverse(
                "zane_api:services.regenerate_deploy_token",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            ),
            data={},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class ViewerSecretFieldsViewTests(ViewerEndpointsTestBase):
    """
    `deploy_token` is enough to deploy through the `AllowAny` webhook routes, so
    a Viewer reading it off the service details payload would have write access.
    Env variables and registry credentials are secrets in the same payload, and
    the change records carry the same values in their `old_value`/`new_value`.
    """

    MEMBER_ONLY_FIELDS = [
        "deploy_token",
        "env_variables",
        "system_env_variables",
        "credentials",
        "container_registry_credentials",
        "unapplied_changes",
    ]
    DEPLOYMENT_MEMBER_ONLY_FIELDS = [
        "changes",
    ]

    def test_member_sees_secret_fields_in_service_details(self):
        project, service = self.create_redis_docker_service()
        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        for field in self.MEMBER_ONLY_FIELDS:
            self.assertIn(field, response.json())

    def test_viewer_does_not_see_secret_fields_in_service_details(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": service.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        jprint(data)
        for field in self.MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, data)

    def test_viewer_does_not_see_secret_fields_in_deployment_snapshot(self):
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment_single",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        snapshot = response.json()["service_snapshot"]
        jprint(snapshot)
        for field in self.MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, snapshot)

    def test_member_sees_changes_in_deployment(self):
        project, service = self.create_redis_docker_service()
        deployment = service.prepare_new_docker_deployment()
        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        response = self.client.get(
            reverse(
                "zane_api:services.deployment_single",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        for field in self.DEPLOYMENT_MEMBER_ONLY_FIELDS:
            self.assertIn(field, response.json())

    def test_viewer_does_not_see_changes_in_deployment(self):
        """
        `changes` records carry the same secrets as the service payload in their
        `old_value` / `new_value` — env variables, source credentials, configs.
        """
        project, service, deployment = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployment_single",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        data = response.json()
        jprint(data)
        for field in self.DEPLOYMENT_MEMBER_ONLY_FIELDS:
            self.assertNotIn(field, data)

    def test_viewer_does_not_see_changes_in_deployment_list(self):
        project, service, _ = self.setup_viewer_with_service()

        response = self.client.get(
            reverse(
                "zane_api:services.deployments_list",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "service_slug": service.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        for deployment in response.json()["results"]:
            for field in self.DEPLOYMENT_MEMBER_ONLY_FIELDS:
                self.assertNotIn(field, deployment)

    def test_deployment_snapshot_stored_in_db_keeps_secret_fields(self):
        """
        The stripping must happen at serialization time only — the snapshot
        persisted by `prepare_new_docker_deployment()` still needs every field
        for redeploys.
        """
        _, service = self.create_redis_docker_service()
        deployment = service.prepare_new_docker_deployment()

        for field in self.MEMBER_ONLY_FIELDS:
            self.assertIn(field, deployment.service_snapshot)  # type: ignore
