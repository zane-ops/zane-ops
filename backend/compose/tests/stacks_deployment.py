from django.urls import reverse
import os
import responses
from rest_framework import status
from unittest.mock import patch

from zane_api.models import Environment
from zane_api.tests.base import FakeDockerClient
from ..models import (
    ComposeStack,
    ComposeStackChange,
    ComposeStackDeployment,
    ComposeStackEnvOverride,
)
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_MULTIPLE_ROUTES,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
)
from typing import cast
from zane_api.utils import jprint
from ..dtos import ComposeStackServiceStatus
import requests
from temporal.helpers import ZaneProxyClient
from django.conf import settings
from temporal.schedules import MonitorComposeStackWorkflow
from temporal.activities import ComposeStackActivities
from compose.dtos import ComposeStackSnapshot
from temporalio import activity
from temporal.shared import ComposeStackBuildDetails
from compose.dtos import ComposeStackUrlRouteDto


from .stacks import ComposeStackAPITestBase


class DeployComposeStackViewTests(ComposeStackAPITestBase):
    def test_deploy_simple_compose_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "my-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(ComposeStack, ComposeStack.objects.filter(slug="my-stack").first())
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.user_content)
        self.assertIsNone(stack.computed_content)

        # Deploy the stack
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify deployment created with snapshot
        deployment = ComposeStackDeployment.objects.filter(stack=stack).first()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)
        self.assertIsNotNone(deployment.stack_snapshot)
        snapshot = cast(dict, deployment.stack_snapshot)
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), snapshot.get("user_content"))
        self.assertIsNotNone(snapshot.get("computed_content"))

        # Verify changes are applied
        stack.refresh_from_db()
        self.assertEqual(DOCKER_COMPOSE_MINIMAL.strip(), stack.user_content)
        self.assertIsNotNone(stack.computed_content)
        self.assertNotEqual(stack.user_content, stack.computed_content)

        # Verify no more unapplied content changes
        unapplied_content_changes = stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
        )
        self.assertEqual(0, unapplied_content_changes.count())

    def test_deploy_compose_with_urls_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx",
            "user_content": DOCKER_COMPOSE_WEB_SERVICE,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(ComposeStack, ComposeStack.objects.filter(slug="nginx").first())
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.urls)

        # Deploy the stack
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify URLs are applied
        stack.refresh_from_db()
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("web", stack_urls)
        routes = cast(list, stack_urls["web"])
        self.assertEqual(len(routes), 1)
        route = cast(dict, routes[0])
        self.assertEqual("hello.127-0-0-1.sslip.io", route["domain"])
        self.assertEqual("/", route["base_path"])
        self.assertEqual(80, route["port"])

    def test_deploy_compose_with_configs_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "nginx-inline-configs",
            "user_content": DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="nginx-inline-configs").first(),
        )
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.configs)

        # Deploy the stack
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify configs are applied
        stack.refresh_from_db()
        self.assertIsNotNone(stack.configs)
        stack_configs = cast(dict, stack.configs)
        self.assertIn("nginx_config", stack_configs)
        expected_content = (
            "user nginx;\n"
            "worker_processes auto;\n"
            "events {\n"
            "  worker_connections 1024;\n"
            "}"
        )
        self.assertEqual(expected_content, stack_configs["nginx_config"])

    def test_deploy_compose_with_env_overrides_apply_changes(self):
        project = self.create_project()

        create_stack_payload = {
            "slug": "placeholder-stack",
            "user_content": DOCKER_COMPOSE_WITH_PLACEHOLDERS,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="placeholder-stack").first(),
        )
        self.assertIsNotNone(stack)
        self.assertEqual(0, stack.env_overrides.count())

        # Deploy the stack
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify env overrides are applied
        stack.refresh_from_db()
        self.assertEqual(5, stack.env_overrides.count())

        # Verify db service env overrides
        db_user = stack.env_overrides.filter(key="POSTGRES_USER").first()
        self.assertIsNotNone(db_user)
        db_password = stack.env_overrides.filter(key="POSTGRES_PASSWORD").first()
        self.assertIsNotNone(db_password)
        db_name = stack.env_overrides.filter(key="POSTGRES_DB").first()
        self.assertIsNotNone(db_name)

        # Verify app service env overrides
        app_token = stack.env_overrides.filter(key="API_TOKEN").first()
        self.assertIsNotNone(app_token)
        app_secret = stack.env_overrides.filter(key="SECRET_KEY").first()
        self.assertIsNotNone(app_secret)


class DeployComposeStackResourcesViewTests(ComposeStackAPITestBase):
    async def acreate_and_deploy_compose_stack(
        self,
        content: str,
        slug="my-stack",
    ):
        project = await self.acreate_project(slug="compose")

        create_stack_payload = {
            "slug": slug,
            "user_content": content,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack, await ComposeStack.objects.filter(slug=slug).afirst()
        )
        self.assertIsNotNone(stack)
        self.assertIsNone(stack.user_content)
        self.assertIsNone(stack.computed_content)

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        await stack.arefresh_from_db()
        print(
            "========= original =========",
            stack.user_content,
            "========= end original =========",
            sep="\n",
        )
        print(
            "========= computed =========",
            stack.computed_content,
            "========= end computed =========",
            sep="\n",
        )

        return project, stack

    async def test_deploy_compose_stack_create_resources(self):
        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)
        jprint(stack.service_statuses)
        jprint(deployment.stack_snapshot)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )
        self.assertIsNotNone(deployment.finished_at)

        # service statuses should be updated
        statuses = cast(dict, stack.service_statuses)
        self.assertGreater(len(statuses), 0)

        name, redis_service = next(iter(stack.service_statuses.items()))
        self.assertEqual("redis", name)
        self.assertEqual(ComposeStackServiceStatus.HEALTHY, redis_service["status"])
        self.assertEqual(1, redis_service["running_replicas"])
        self.assertEqual(1, redis_service["desired_replicas"])
        self.assertEqual(1, len(redis_service["tasks"]))

        # service should be created
        services: list[FakeDockerClient.FakeService] = []
        for service in statuses:
            try:
                services.append(
                    self.fake_docker_client.services_get(
                        f"{stack.name}_{stack.hash_prefix}_{service}"
                    )
                )
            except Exception:
                pass
        self.assertGreater(len(services), 0)

    async def test_deploy_compose_stack_with_inline_configs_creates_config_files(self):
        # Track config files written during deployment
        captured_config_files: dict[str, str] = {}

        original_create_files = (
            ComposeStackActivities.create_files_in_docker_stack_folder
        )

        @activity.defn(name="create_files_in_docker_stack_folder")
        async def capture_config_files_wrapper(self_instance, details: dict):
            build_details = ComposeStackBuildDetails.from_dict(details)

            # Call original implementation
            await original_create_files(self_instance, build_details)

            # Check for config files in tmp_build_dir
            tmp_dir = build_details.tmp_build_dir
            for filename in os.listdir(tmp_dir):
                if filename.endswith(".conf"):
                    filepath = os.path.join(tmp_dir, filename)
                    with open(filepath, "r") as f:
                        captured_config_files[filename] = f.read()

        with patch.object(
            ComposeStackActivities,
            "create_files_in_docker_stack_folder",
            capture_config_files_wrapper,
        ):
            _, stack = await self.acreate_and_deploy_compose_stack(
                content=DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
                slug="nginx-configs",
            )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify configs were applied to the stack
        self.assertIsNotNone(stack.configs)
        stack_configs = cast(dict, stack.configs)
        self.assertIn("nginx_config", stack_configs)

        # Verify the config content matches what was defined
        expected_content = (
            "user nginx;\n"
            "worker_processes auto;\n"
            "events {\n"
            "  worker_connections 1024;\n"
            "}"
        )
        self.assertEqual(expected_content, stack_configs["nginx_config"])

        # Verify config file was created with correct name format: {hash_prefix}_{config_name}.conf
        expected_filename = f"{stack.hash_prefix}_nginx_config.conf"
        self.assertIn(
            expected_filename,
            captured_config_files,
            f"Expected config file '{expected_filename}' to be created, got: {list(captured_config_files.keys())}",
        )

        # Verify file content matches
        self.assertEqual(expected_content, captured_config_files[expected_filename])

    @responses.activate()
    async def test_deploy_compose_stack_with_routes_exposes_to_http(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE,
            slug="nginx-routes",
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify URLs were applied to the stack
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("web", stack_urls)

        routes = cast(list, stack_urls["web"])
        self.assertEqual(len(routes), 1)

        route = cast(dict, routes[0])
        self.assertEqual("hello.127-0-0-1.sslip.io", route["domain"])
        self.assertEqual("/", route["base_path"])
        self.assertEqual(80, route["port"])

        # Verify the route was registered in Caddy
        # The route ID for compose stacks follows the pattern: stack_id-service_name-route_index
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(200, response.status_code)
        jprint(response.json())

    @responses.activate()
    async def test_deploy_compose_stack_with_multiple_routes(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MULTIPLE_ROUTES,
            slug="api-routes",
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify URLs were applied
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("api", stack_urls)

        routes = cast(list, stack_urls["api"])
        self.assertEqual(len(routes), 2)

        # Verify first route (api.example.com/)
        route_0 = cast(dict, routes[0])
        self.assertEqual("api.example.com", route_0["domain"])
        self.assertEqual("/", route_0["base_path"])

        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="api",
                url=ComposeStackUrlRouteDto.from_dict(route_0),
            )
        )
        self.assertEqual(200, response.status_code)
        jprint(response.json())

        # Verify second route (example.com/api)
        route_1 = cast(dict, routes[1])
        self.assertEqual("example.com", route_1["domain"])
        self.assertEqual("/api", route_1["base_path"])

        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="api",
                url=ComposeStackUrlRouteDto.from_dict(route_1),
            )
        )
        self.assertEqual(200, response.status_code)
        jprint(response.json())

    async def test_deploy_compose_stack_creates_monitor_schedule(self):
        _, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL,
            slug="healthcheck-stack",
        )

        deployment = await stack.deployments.afirst()
        self.assertIsNotNone(deployment)
        deployment = cast(ComposeStackDeployment, deployment)

        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
        )

        # Verify the healthcheck schedule was created
        schedule_handle = self.get_workflow_schedule_by_id(stack.monitor_schedule_id)
        self.assertIsNotNone(schedule_handle)

    async def test_monitor_compose_stack_workflow_updates_service_statuses(self):
        async with self.workflowEnvironment() as env:
            _, stack = await self.acreate_and_deploy_compose_stack(
                content=DOCKER_COMPOSE_MINIMAL,
                slug="monitor-stack",
            )

            deployment = await stack.deployments.afirst()
            self.assertIsNotNone(deployment)
            deployment = cast(ComposeStackDeployment, deployment)

            self.assertEqual(
                ComposeStackDeployment.DeploymentStatus.FINISHED, deployment.status
            )

            # Verify service statuses are initially set after deployment
            statuses = cast(dict, stack.service_statuses)
            self.assertGreater(len(statuses), 0)

            # Clear service statuses to simulate stale state
            stack.service_statuses = {}
            await stack.asave()

            # Refresh to verify it was cleared
            await stack.arefresh_from_db()
            self.assertEqual({}, stack.service_statuses)

            # Run the monitor workflow directly
            snapshot = ComposeStackSnapshot(
                id=stack.id,
                name=stack.name,
                slug=stack.slug,
                hash_prefix=stack.hash_prefix,
                monitor_schedule_id=stack.monitor_schedule_id,
                network_alias_prefix=stack.network_alias_prefix,
                user_content=stack.user_content or "",
                computed_content=stack.computed_content or "",
            )

            healthcheck = await env.client.execute_workflow(
                workflow=MonitorComposeStackWorkflow.run,
                arg=snapshot,
                id=stack.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )

            jprint(healthcheck.services)

            # Refresh and verify service statuses are updated
            await stack.arefresh_from_db()
            statuses = cast(dict, stack.service_statuses)
            self.assertGreater(len(statuses), 0)

            name, redis_service = next(iter(statuses.items()))
            self.assertEqual("redis", name)
            self.assertEqual(ComposeStackServiceStatus.HEALTHY, redis_service["status"])
            self.assertEqual(1, redis_service["running_replicas"])
            self.assertEqual(1, redis_service["desired_replicas"])

    async def test_queue_multiple_deploys_are_all_deployed(self):
        project, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL,
            slug="monitor-stack",
        )

        # Verify first deployment exists
        first_deployment = await stack.deployments.afirst()
        self.assertIsNotNone(first_deployment)
        first_deployment = cast(ComposeStackDeployment, first_deployment)
        self.assertEqual(
            ComposeStackDeployment.DeploymentStatus.FINISHED, first_deployment.status
        )

        # Manually queue additional deployments
        await ComposeStackDeployment.objects.acreate(
            commit_message="second deployment",
            stack=stack,
            stack_snapshot=first_deployment.stack_snapshot,
        )
        await ComposeStackDeployment.objects.acreate(
            commit_message="third deployment",
            stack=stack,
            stack_snapshot=first_deployment.stack_snapshot,
        )

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            await stack.deployments.filter(
                status=ComposeStackDeployment.DeploymentStatus.QUEUED
            ).acount(),
            0,
        )
        self.assertEqual(
            await stack.deployments.filter(
                status=ComposeStackDeployment.DeploymentStatus.FINISHED
            ).acount(),
            4,
        )


class ArchiveComposeStackResourcesViewTests(ComposeStackAPITestBase):
    def test_archive_stack_delete_stack_and_deployments(self):
        project = self.create_project()

        # Create and deploy a stack
        create_stack_payload = {
            "slug": "archive-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack, ComposeStack.objects.filter(slug="archive-stack").first()
        )
        self.assertIsNotNone(stack)
        stack_id = stack.id

        # Deploy the stack
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify deployment exists
        deployment_count = ComposeStackDeployment.objects.filter(stack=stack).count()
        self.assertGreater(deployment_count, 0)

        # Archive the stack
        response = self.client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify stack is deleted
        self.assertIsNone(ComposeStack.objects.filter(id=stack_id).first())

        # Verify deployments are deleted
        self.assertEqual(
            0, ComposeStackDeployment.objects.filter(stack_id=stack_id).count()
        )

    def test_archive_stack_delete_env_overrides(self):
        project = self.create_project()

        # Create and deploy a stack with env overrides
        create_stack_payload = {
            "slug": "env-override-stack",
            "user_content": DOCKER_COMPOSE_WITH_PLACEHOLDERS,
        }

        response = self.client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            ComposeStack.objects.filter(slug="env-override-stack").first(),
        )
        self.assertIsNotNone(stack)
        stack_id = stack.id

        # Deploy the stack to apply env overrides
        response = self.client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify env overrides exist
        stack.refresh_from_db()
        self.assertGreater(stack.env_overrides.count(), 0)

        # Archive the stack
        response = self.client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify stack and env overrides are deleted
        self.assertIsNone(ComposeStack.objects.filter(id=stack_id).first())

        self.assertEqual(
            0, ComposeStackEnvOverride.objects.filter(stack_id=stack_id).count()
        )

    @responses.activate()
    async def test_archive_stack_delete_services(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack with inline configs
        create_stack_payload = {
            "slug": "config-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="config-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_name = stack.name

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify configs exist
        await stack.arefresh_from_db()
        self.assertIsNotNone(stack.configs)

        # Archive the stack
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify config stack is deleted
        service_list = self.fake_docker_client.services_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(service_list))

    @responses.activate()
    async def test_archive_stack_delete_attached_configs(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack with inline configs
        create_stack_payload = {
            "slug": "config-stack",
            "user_content": DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="config-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_name = stack.name

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify configs exist
        await stack.arefresh_from_db()
        self.assertIsNotNone(stack.configs)

        # Archive the stack
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify config stack is deleted
        config_list = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(config_list))

    @responses.activate()
    async def test_archive_stack_delete_attached_volumes(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack with volumes
        create_stack_payload = {
            "slug": "volume-stack",
            "user_content": DOCKER_COMPOSE_SIMPLE_DB,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="volume-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_id = stack.id
        stack_name = stack.name

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Archive the stack
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify stack is deleted
        self.assertIsNone(await ComposeStack.objects.filter(id=stack_id).afirst())

        # Verify Docker volumes with zane-stack label are removed
        volumes = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(0, len(volumes))

    @responses.activate()
    async def test_archive_stack_delete_urls_in_proxy(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack with URLs
        create_stack_payload = {
            "slug": "url-stack",
            "user_content": DOCKER_COMPOSE_WEB_SERVICE,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="url-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_id = stack.id

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify URLs exist
        await stack.arefresh_from_db()
        self.assertIsNotNone(stack.urls)
        stack_urls = cast(dict, stack.urls)
        self.assertIn("web", stack_urls)

        # Get route info before archiving
        routes = cast(list, stack_urls["web"])
        route = cast(dict, routes[0])

        # Verify route is registered in Caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack.id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(200, response.status_code)

        # Archive the stack
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify stack is deleted
        self.assertIsNone(await ComposeStack.objects.filter(id=stack_id).afirst())

        # Verify route is removed from Caddy
        response = requests.get(
            ZaneProxyClient.get_uri_for_compose_stack_service(
                stack_id=stack_id,
                service_name="web",
                url=ComposeStackUrlRouteDto.from_dict(route),
            )
        )
        self.assertEqual(404, response.status_code)

    @responses.activate()
    async def test_archive_stack_with_delete_configs_false_keeps_configs(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack with inline configs
        create_stack_payload = {
            "slug": "keep-config-stack",
            "user_content": DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="keep-config-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_name = stack.name

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify configs exist before archiving
        await stack.arefresh_from_db()
        self.assertIsNotNone(stack.configs)

        config_list_before = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertGreater(len(config_list_before), 0)

        # Archive the stack with delete_configs=False
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"delete_configs": False},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify configs are NOT deleted
        config_list_after = self.fake_docker_client.config_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(len(config_list_before), len(config_list_after))

    @responses.activate()
    async def test_archive_compose_stack_deletes_monitor_schedule(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack
        create_stack_payload = {
            "slug": "monitor-stack",
            "user_content": DOCKER_COMPOSE_MINIMAL,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="monitor-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_id = stack.id
        monitor_schedule_id = stack.monitor_schedule_id

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify monitor schedule was created
        schedule_handle = self.get_workflow_schedule_by_id(monitor_schedule_id)
        self.assertIsNotNone(schedule_handle)

        # Archive the stack
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify stack is deleted
        self.assertIsNone(await ComposeStack.objects.filter(id=stack_id).afirst())

        # Verify monitor schedule is deleted
        self.assertIsNone(self.get_workflow_schedule_by_id(monitor_schedule_id))

    @responses.activate()
    async def test_archive_stack_with_delete_volumes_false_keeps_volumes(self):
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        project = await self.acreate_project()

        # Create and deploy a stack with volumes
        create_stack_payload = {
            "slug": "keep-volume-stack",
            "user_content": DOCKER_COMPOSE_SIMPLE_DB,
        }

        response = await self.async_client.post(
            reverse(
                "compose:stacks.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                },
            ),
            data=create_stack_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        stack = cast(
            ComposeStack,
            await ComposeStack.objects.filter(slug="keep-volume-stack").afirst(),
        )
        self.assertIsNotNone(stack)
        stack_name = stack.name

        # Deploy the stack
        response = await self.async_client.put(
            reverse(
                "compose:stacks.deploy",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Verify volumes exist before archiving
        volumes_before = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertGreater(len(volumes_before), 0)

        # Archive the stack with delete_volumes=False
        response = await self.async_client.delete(
            reverse(
                "compose:stacks.archive",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": Environment.PRODUCTION_ENV_NAME,
                    "slug": stack.slug,
                },
            ),
            data={"delete_volumes": False},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Verify volumes are NOT deleted
        volumes_after = self.fake_docker_client.volumes_list(
            filters={"label": [f"com.docker.stack.namespace={stack_name}"]}
        )
        self.assertEqual(len(volumes_before), len(volumes_after))
