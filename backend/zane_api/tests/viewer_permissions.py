from django.urls import reverse
from rest_framework import status

from ..models import (
    Config,
    Environment,
    GitApp,
    PreviewEnvMetadata,
    Project,
    Service,
    WorkspaceMembership,
    WorkspaceRole,
)
from ..utils import generate_random_chars, jprint
from .base import AuthAPITestCase
from git_connectors.models import GitHubApp
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

    def test_viewer_can_view_server_resource_limits(self):
        self.setup_viewer_with_service()
        response = self.client.get(reverse("zane_api:server.resource_limits"))
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

    def test_viewer_can_view_environment_details(self):
        """
        The environment is the container for the service list a Viewer *is*
        granted — denying it makes that surface unreachable.
        """
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


EMPTY_SET = frozenset()


class ViewerSecretFieldsViewTests(ViewerEndpointsTestBase):
    """
    `deploy_token` is enough to deploy through the `AllowAny` webhook routes, so
    a Viewer reading it off the service details payload would have write access.
    Env variables and registry credentials are secrets in the same payload, and
    the change records carry the same values in their `old_value`/`new_value`.
    """

    # The tests below assert on these sets against `payload.keys()`, which is
    # itself a set-like view, using set algebra (union, intersection, difference, etc.):
    #
    #   FIELDS & payload.keys()  -> intersection: Are there secrets fields included in the response for a viewer ?
    #                               Should be empty for a viewer, since any field in common means the field wasn't stripped.
    #
    #   FIELDS - payload.keys()  -> difference: Is there any field missing_fields in the response for a member ?
    #                               Should be empty for a member, since any element missing_fields means the field was wrongly stripped.
    #
    # Both are asserted equal to the empty set rather than tested per element,
    # so a failure reports every offending field at once.
    SERVICE_MEMBER_ONLY_FIELDS = frozenset(
        [
            "deploy_token",
            "env_variables",
            "system_env_variables",
            "credentials",
            "container_registry_credentials",
            "unapplied_changes",
        ]
    )
    DEPLOYMENT_MEMBER_ONLY_FIELDS = frozenset(["changes"])
    ENVIRONMENT_MEMBER_ONLY_FIELDS = frozenset(["variables"])
    PREVIEW_METADATA_MEMBER_ONLY_FIELDS = frozenset(["auth_user", "auth_password"])
    CONFIG_MEMBER_ONLY_FIELDS = frozenset(["contents"])

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
        missing_fields = self.SERVICE_MEMBER_ONLY_FIELDS - response.json().keys()
        self.assertEqual(frozenset(), missing_fields)

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
        non_stripped_fields = self.SERVICE_MEMBER_ONLY_FIELDS & data.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

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
        non_stripped_fields = self.SERVICE_MEMBER_ONLY_FIELDS & snapshot.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

    def test_member_sees_secret_fields_in_deployment(self):
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
        data = response.json()
        jprint(data)

        # Check that secret fields from deployment are included
        missing_fields = self.DEPLOYMENT_MEMBER_ONLY_FIELDS - data.keys()
        self.assertEqual(EMPTY_SET, missing_fields)

        # Also Check that secret fields from snapshot are included
        missing_fields = (
            self.SERVICE_MEMBER_ONLY_FIELDS - data["service_snapshot"].keys()
        )
        self.assertEqual(EMPTY_SET, missing_fields)

    def test_viewer_does_not_see_deployment_secret_fields(self):
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

        deployment = response.json()
        jprint(deployment)

        # Check that deployment does not contain secret fields
        non_stripped_fields = self.DEPLOYMENT_MEMBER_ONLY_FIELDS & deployment.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

        # Check that snapshots also do not contain secret fields
        snapshot = deployment["service_snapshot"]
        non_stripped_fields = self.SERVICE_MEMBER_ONLY_FIELDS & snapshot.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

    def test_viewer_does_not_see_deployment_secret_fields_in_deployment_list(self):
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
        data = response.json()
        jprint(data)

        for deployment in data["results"]:
            # Check that deployment does not contain secret fields
            non_stripped_fields = self.DEPLOYMENT_MEMBER_ONLY_FIELDS & deployment.keys()
            self.assertEqual(EMPTY_SET, non_stripped_fields)
            # Check that snapshots also do not contain secret fields
            snapshot = deployment["service_snapshot"]
            non_stripped_fields = self.SERVICE_MEMBER_ONLY_FIELDS & snapshot.keys()
            self.assertEqual(EMPTY_SET, non_stripped_fields)

    def test_deployment_snapshot_stored_in_db_keeps_secret_fields(self):
        """
        The stripping must happen at serialization time only — the snapshot
        persisted by `prepare_new_docker_deployment()` still needs every field
        for redeploys.
        """
        _, service = self.create_redis_docker_service()
        deployment = service.prepare_new_docker_deployment()

        missing_fields = (
            self.SERVICE_MEMBER_ONLY_FIELDS - deployment.service_snapshot.keys()  # type: ignore
        )
        self.assertEqual(EMPTY_SET, missing_fields)

    def test_member_sees_variables_in_environment_details(self):
        project, _ = self.create_redis_docker_service()
        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        response = self.client.get(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={
                    "slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        jprint(data)

        missing_fields = self.ENVIRONMENT_MEMBER_ONLY_FIELDS - data.keys()
        self.assertEqual(EMPTY_SET, missing_fields)

    def test_viewer_does_not_see_variables_in_environment_details(self):
        """
        Shared env variables propagate to every service in the environment —
        a Viewer gets the environment so the service list is reachable, but not
        the values it carries.
        """
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
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        jprint(data)

        non_stripped_fields = self.ENVIRONMENT_MEMBER_ONLY_FIELDS & data.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)

    def create_preview_environment(self, project: Project, auth_password: str):
        """
        A preview environment whose public URL is protected by HTTP basic auth —
        the credentials Caddy enforces live on `PreviewEnvMetadata`.
        """
        service = Service.objects.filter(project=project).get()
        github = GitHubApp.objects.create(
            webhook_secret=generate_random_chars(10),
            app_id=1,
            name="zaneops",
            client_id=generate_random_chars(10),
            client_secret=generate_random_chars(10),
            private_key=generate_random_chars(10),
            app_url="https://github.com/apps/zaneops",
            installation_id=1,
        )
        git_app = GitApp.objects.create(github=github, workspace=project.workspace)

        preview_metadata = PreviewEnvMetadata.objects.create(
            service=service,
            git_app=git_app,
            template=project.preview_templates.get(is_default=True),
            branch_name="main",
            external_url="https://preview.zaneops.local",
            head_repository_url="https://github.com/zane-ops/docs",
            source_trigger=Environment.PreviewSourceTrigger.API,
            auth_enabled=True,
            auth_user="preview",
            auth_password=auth_password,
        )
        return Environment.objects.create(
            name="preview-pr-1",
            project=project,
            is_preview=True,
            preview_metadata=preview_metadata,
        )

    def test_member_sees_preview_auth_credentials(self):
        project, service = self.create_redis_docker_service()
        environment = self.create_preview_environment(project, auth_password="hunter2")
        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        response = self.client.get(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": environment.name},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        jprint(data)

        missing_fields = (
            self.PREVIEW_METADATA_MEMBER_ONLY_FIELDS - data["preview_metadata"].keys()
        )
        self.assertEqual(EMPTY_SET, missing_fields)
        self.assertEqual("hunter2", data["preview_metadata"]["auth_password"])

    def test_viewer_does_not_see_preview_auth_credentials(self):
        """
        `auth_password` is the basic-auth password Caddy enforces on the preview
        URL — a Viewer reading it off the environment payload walks straight
        past the protection, same shape as the `deploy_token` hole.
        """
        project, service = self.create_redis_docker_service()
        environment = self.create_preview_environment(project, auth_password="hunter2")

        membership = WorkspaceMembership.objects.get(workspace=project.workspace)
        membership.role = WorkspaceRole.VIEWER
        membership.save()
        membership.accessible_projects.add(project)

        response = self.client.get(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": environment.name},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        jprint(data)

        non_stripped_fields = (
            self.PREVIEW_METADATA_MEMBER_ONLY_FIELDS & data["preview_metadata"].keys()
        )
        self.assertEqual(EMPTY_SET, non_stripped_fields)
        # the fact that it *is* protected stays visible
        self.assertTrue(data["preview_metadata"]["auth_enabled"])

    def test_viewer_does_not_see_preview_auth_credentials_in_service_details(self):
        """
        Service details embed the environment through `ServiceSerializer`, which
        nests the *simple* preview metadata serializer — a different class from
        the one environment-details uses, so it needs its own coverage.
        """
        project, service = self.create_redis_docker_service()
        environment = self.create_preview_environment(project, auth_password="hunter2")
        service.environment = environment
        service.save()

        membership = WorkspaceMembership.objects.get(workspace=project.workspace)
        membership.role = WorkspaceRole.VIEWER
        membership.save()
        membership.accessible_projects.add(project)

        response = self.client.get(
            reverse(
                "zane_api:services.details",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": environment.name,
                    "slug": service.slug,
                },
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        jprint(data)

        preview_metadata = data["environment"]["preview_metadata"]
        non_stripped_fields = (
            self.PREVIEW_METADATA_MEMBER_ONLY_FIELDS & preview_metadata.keys()
        )
        self.assertEqual(EMPTY_SET, non_stripped_fields)
        self.assertTrue(preview_metadata["auth_enabled"])

    def test_deployment_snapshot_stored_in_db_keeps_preview_auth_credentials(self):
        """
        The snapshot feeds `EnvironmentDto.from_dict()`, which passes
        `auth_user` / `auth_password` to Caddy on every redeploy. Stripping them
        at write time would silently unprotect preview URLs.
        """
        project, service = self.create_redis_docker_service()
        environment = self.create_preview_environment(project, auth_password="hunter2")
        service.environment = environment
        service.save()

        deployment = service.prepare_new_docker_deployment()
        preview_metadata = deployment.service_snapshot["environment"][  # type: ignore
            "preview_metadata"
        ]
        jprint(preview_metadata)

        missing_fields = (
            self.PREVIEW_METADATA_MEMBER_ONLY_FIELDS - preview_metadata.keys()
        )
        self.assertEqual(EMPTY_SET, missing_fields)
        self.assertEqual("hunter2", preview_metadata["auth_password"])

    def add_config_to_service(self, service: Service, contents: str):
        """A config file mounted into the service — its body can hold anything."""
        config = Config.objects.create(
            name="caddyfile",
            mount_path="/etc/caddy/Caddyfile",
            contents=contents,
        )
        service.configs.add(config)
        return config

    def get_service_details(self, project: Project, service: Service):
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
        return response.json()

    def test_member_sees_config_contents_in_service_details(self):
        project, service = self.create_redis_docker_service()
        self.add_config_to_service(service, contents="basicauth { admin hunter2 }")
        WorkspaceMembership.objects.filter(workspace=project.workspace).update(
            role=WorkspaceRole.MEMBER
        )

        data = self.get_service_details(project, service)
        jprint(data["configs"])
        self.assertEqual(1, len(data["configs"]))
        missing_fields = self.CONFIG_MEMBER_ONLY_FIELDS - data["configs"][0].keys()
        self.assertEqual(EMPTY_SET, missing_fields)

    def test_viewer_does_not_see_config_contents_in_service_details(self):
        """
        Config files are arbitrary text — Caddyfiles with basic-auth hashes,
        app config with connection strings. The name and mount path are safe,
        the body is not.
        """
        project, service, _ = self.setup_viewer_with_service()
        self.add_config_to_service(service, contents="basicauth { admin hunter2 }")

        data = self.get_service_details(project, service)
        jprint(data["configs"])
        self.assertEqual(1, len(data["configs"]))
        config = data["configs"][0]
        non_stripped_fields = self.CONFIG_MEMBER_ONLY_FIELDS & config.keys()
        self.assertEqual(EMPTY_SET, non_stripped_fields)
        # the config is still listed, just without its body
        self.assertEqual("caddyfile", config["name"])

    def test_deployment_snapshot_stored_in_db_keeps_config_contents(self):
        _, service = self.create_redis_docker_service()
        self.add_config_to_service(service, contents="basicauth { admin hunter2 }")

        deployment = service.prepare_new_docker_deployment()
        configs = deployment.service_snapshot["configs"]  # type: ignore
        jprint(configs)
        self.assertEqual(
            "basicauth { admin hunter2 }",
            configs[0]["contents"],
        )
