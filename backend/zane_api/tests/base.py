import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Generator, List, Callable, Mapping, Optional, Self
from unittest.mock import MagicMock, patch, AsyncMock

import docker.errors
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import AsyncClient  # type: ignore
from django.test import TestCase, override_settings
from django.urls import reverse
from docker.types import (
    EndpointSpec,
    Resources,
    NetworkAttachmentConfig,
    ConfigReference,
)
from asgiref.sync import sync_to_async
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from search.loki_client import LokiSearchClient

from ..models import (
    Project,
    DeploymentChange,
    Service,
    Deployment,
    Volume,
    Config,
    URL,
    Environment,
)
from ..temporal.helpers import (
    get_network_resource_name,
    get_env_network_resource_name,
    DockerImageResultFromRegistry,
    SERVER_RESOURCE_LIMIT_COMMAND,
    get_config_resource_name,
)
from ..temporal import get_workflows_and_activities

from ..temporal.activities import (
    get_swarm_service_name_for_deployment,
    get_volume_resource_name,
)
from ..utils import Colors, find_item_in_list, random_word
from git import GitCommandError


class CustomAPIClient(APIClient):
    def __init__(self, parent: TestCase, **defaults):
        super().__init__(enforce_csrf_checks=False, **defaults)
        self.parent = parent

    def post(
        self,
        path,
        data=None,
        format=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)
        response = super().post(
            path=path,
            data=data,
            format=format,
            headers=headers,
            follow=follow,
            content_type=(
                content_type if content_type is not None else "application/json"
            ),
            **extra,
        )
        return response

    def put(
        self,
        path,
        data=None,
        format=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)

        response = super().put(
            path=path,
            data=data,
            format=format,
            content_type=(
                content_type if content_type is not None else "application/json"
            ),
            follow=follow,
            headers=headers,
            **extra,
        )
        return response

    def patch(
        self,
        path,
        data=None,
        format=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)
        response = super().patch(
            path=path,
            data=data,
            format=format,
            content_type=(
                content_type if content_type is not None else "application/json"
            ),
            follow=follow,
            headers=headers,
            **extra,
        )
        return response

    def delete(
        self,
        path,
        data=None,
        format=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)
        response = super().delete(
            path=path,
            data=data,
            format=format,
            content_type=(
                content_type if content_type is not None else "application/json"
            ),
            follow=follow,
            headers=headers,
            **extra,
        )
        return response


class AsyncCustomAPIClient(AsyncClient):
    def __init__(self, parent: "AuthAPITestCase", **defaults):
        super().__init__(enforce_csrf_checks=False, **defaults)
        self.parent = parent

    async def post(
        self,
        path,
        data=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)
        async with self.parent.acaptureCommitCallbacks(execute=True):
            response = await super().post(
                path=path,
                data=data,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
                follow=follow,
                headers=headers,
                **extra,
            )
        return response

    async def put(
        self,
        path,
        data=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)

        async with self.parent.acaptureCommitCallbacks(execute=True):
            response = await super().put(
                path=path,
                data=data,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
                follow=follow,
                headers=headers,
                **extra,
            )
        return response

    async def patch(
        self,
        path,
        data=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)

        async with self.parent.acaptureCommitCallbacks(execute=True):
            response = await super().patch(
                path=path,
                data=data,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
                follow=follow,
                headers=headers,
                **extra,
            )
        return response

    async def delete(
        self,
        path,
        data=None,
        content_type=None,
        follow=False,
        headers=None,
        **extra,
    ):
        if type(data) is not str:
            data = json.dumps(data)
        async with self.parent.acaptureCommitCallbacks(execute=True):
            response = await super().delete(
                path=path,
                data=data,
                content_type=(
                    content_type if content_type is not None else "application/json"
                ),
                follow=follow,
                headers=headers,
                **extra,
            )
        return response


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    # DEBUG=True,  # uncomment for debugging temporalio workflows
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_BROKER_URL="memory://",
    CELERY_TASK_STORE_EAGER_RESULT=True,
)
class APITestCase(TestCase):
    def setUp(self):
        self.client = CustomAPIClient(parent=self)
        self.async_client = AsyncCustomAPIClient(parent=self)  # type: ignore
        self.fake_docker_client = FakeDockerClient()
        self.fake_git = FakeGit()
        self.search_client = LokiSearchClient(host=settings.LOKI_HOST)
        self.LOKI_APP_NAME = f"testing-{random_word()}"
        settings_ctx = override_settings(
            LOKI_APP_NAME=self.LOKI_APP_NAME,
        )
        settings_ctx.__enter__()

        # these functions are always patched
        patch(
            "zane_api.temporal.activities.asyncio.sleep", new_callable=AsyncMock
        ).start()
        patch(
            "zane_api.temporal.activities.main_activities.get_docker_client",
            return_value=self.fake_docker_client,
        ).start()
        patch(
            "zane_api.temporal.activities.git_activities.get_docker_client",
            return_value=self.fake_docker_client,
        ).start()
        patch(
            "zane_api.temporal.helpers.get_docker_client",
            return_value=self.fake_docker_client,
        ).start()

        patch(
            "zane_api.temporal.activities.service_auto_update.get_docker_client",
            return_value=self.fake_docker_client,
        ).start()

        patch(
            "zane_api.git_client.Git",
            return_value=self.fake_git,
        ).start()

        patch(
            "zane_api.git_client.Repo.clone_from",
            side_effect=self.fake_git.clone_from,
        ).start()

        patch(
            "zane_api.temporal.schedules.activities.get_docker_client",
            return_value=self.fake_docker_client,
        ).start()

        self.addCleanup(patch.stopall)
        self.addCleanup(lambda: settings_ctx.__exit__(None, None, None))
        self.addCleanup(lambda: self.search_client.delete())

    def tearDown(self):
        cache.clear()

    def assertDictContainsSubset(
        self,
        subset: Mapping[Any, Any],
        dictionary: Mapping[Any, Any],
        msg: object = None,
    ):
        extracted_subset = dict(
            [
                (key, dictionary[key])
                for key in subset.keys()
                if key in dictionary.keys()
            ]
        )
        self.assertEqual(subset, extracted_subset, msg)


@dataclass
class WorkflowScheduleHandle:
    id: str
    workflow: Any
    interval: timedelta
    is_running: bool = True
    note: Optional[str] = None


class AuthAPITestCase(APITestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username="Fredkiss3", password="password")
        self.commit_callbacks: List[Callable] = []
        self.workflow_env: Optional[WorkflowEnvironment] = None
        self.workflow_schedules: List[WorkflowScheduleHandle] = []

    def get_workflow_schedule_by_id(self, id: str):
        return find_item_in_list(
            lambda handle: handle.id == id, self.workflow_schedules
        )

    def loginUser(self):
        self.client.login(username="Fredkiss3", password="password")
        user = User.objects.get(username="Fredkiss3")
        Token.objects.get_or_create(user=user)
        return user

    async def aLoginUser(self):
        await self.async_client.alogin(username="Fredkiss3", password="password")
        user = await User.objects.aget(username="Fredkiss3")
        await Token.objects.aget_or_create(user=user)
        return user

    @asynccontextmanager
    async def workflowEnvironment(
        self, task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE, skip_time=True
    ):
        env = await WorkflowEnvironment.start_time_skipping()
        await env.__aenter__()
        worker = Worker(
            env.client,
            task_queue=task_queue,
            **get_workflows_and_activities(),  # type: ignore
        )
        await worker.__aenter__()

        def collect_commit_callbacks(func: Callable):
            self.commit_callbacks.append(func)

        patch_temporal_client = patch(
            "zane_api.temporal.main.get_temporalio_client", new_callable=AsyncMock
        )

        async def create_schedule(
            id: str, interval: timedelta, workflow: Any, *args, **kwargs
        ):
            self.workflow_schedules.append(
                WorkflowScheduleHandle(id, interval=interval, workflow=workflow)
            )

        async def pause_schedule(id: str, note: str | None = None):
            schedule_handle = find_item_in_list(
                lambda handle: handle.id == id, self.workflow_schedules
            )
            if schedule_handle is not None:
                schedule_handle.is_running = False
                schedule_handle.note = note

        async def unpause_schedule(id: str, note: str | None = None):
            schedule_handle = find_item_in_list(
                lambda handle: handle.id == id, self.workflow_schedules
            )
            if schedule_handle is not None:
                schedule_handle.is_running = True
                schedule_handle.note = note

        async def delete_schedule(id: str):
            schedule_handle = find_item_in_list(
                lambda handle: handle.id == id, self.workflow_schedules
            )
            if schedule_handle is not None:
                self.workflow_schedules.remove(schedule_handle)

        patch_temporal_create_schedule = patch(
            "zane_api.temporal.activities.main_activities.create_schedule",
            side_effect=create_schedule,
        )
        patch_temporal_pause_schedule = patch(
            "zane_api.temporal.activities.main_activities.pause_schedule",
            side_effect=pause_schedule,
        )
        patch_temporal_unpause_schedule = patch(
            "zane_api.temporal.activities.main_activities.unpause_schedule",
            side_effect=unpause_schedule,
        )
        patch_temporal_delete_schedule = patch(
            "zane_api.temporal.activities.main_activities.delete_schedule",
            side_effect=delete_schedule,
        )
        patch_temporal_create_schedule.start()
        patch_temporal_pause_schedule.start()
        patch_temporal_unpause_schedule.start()
        patch_temporal_delete_schedule.start()
        mock_get_client = patch_temporal_client.start()
        mock_client = mock_get_client.return_value
        mock_client.start_workflow.side_effect = env.client.execute_workflow
        mock_client.get_workflow_handle_for = env.client.get_workflow_handle_for

        patch_transaction_on_commit = patch(
            "django.db.transaction.on_commit", side_effect=collect_commit_callbacks
        )
        patch_transaction_on_commit.start()
        self.workflow_env = env
        try:
            yield env
        finally:
            self.workflow_env = None
            patch_temporal_client.stop()
            patch_transaction_on_commit.stop()
            patch_temporal_create_schedule.stop()
            patch_temporal_pause_schedule.stop()
            patch_temporal_unpause_schedule.stop()
            patch_temporal_delete_schedule.stop()
            await worker.__aexit__(None, None, None)
            await env.__aexit__(None, None, None)

    @asynccontextmanager
    async def acaptureCommitCallbacks(self, execute=False):
        self.commit_callbacks = []
        if self.workflow_env is None:
            async with self.workflowEnvironment():
                yield
                loop = asyncio.get_running_loop()
                with ThreadPoolExecutor() as pool:
                    for callback in self.commit_callbacks:
                        if execute:
                            # Run callback in another thread because it is decorated with `@async_to_sync()`
                            await loop.run_in_executor(pool, callback)
        else:
            yield
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as pool:
                for callback in self.commit_callbacks:
                    if execute:
                        # Run callback in another thread because it is decorated with `@async_to_sync()`
                        await loop.run_in_executor(pool, callback)
        self.commit_callbacks = []

    def create_and_deploy_redis_docker_service(
        self,
        with_healthcheck: bool = False,
        other_changes: list[DeploymentChange] | None = None,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        project = Project.objects.get(slug="zaneops")

        create_service_payload = {"slug": "redis", "image": "valkey/valkey:7.2-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        service = Service.objects.get(slug="redis")

        other_changes = other_changes if other_changes is not None else []
        if with_healthcheck:
            other_changes.append(
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "valkey-cli validate",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                    },
                    service=service,
                ),
            )

        for change in other_changes:
            change.service = service
        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "image": "valkey/valkey:7.2-alpine",
                    },
                    service=service,
                ),
            ]
            + other_changes
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        service.refresh_from_db()
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return project, service

    async def acreate_and_deploy_redis_docker_service(
        self,
        with_healthcheck: bool = False,
        other_changes: list[DeploymentChange] | None = None,
    ) -> tuple[Project, Service]:
        owner = await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = await Project.objects.aget(slug="zaneops", owner=owner)

        create_service_payload = {"slug": "redis", "image": "valkey/valkey:7.2-alpine"}
        response = await self.async_client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service: Service = await Service.objects.aget(slug="redis")

        other_changes = other_changes if other_changes is not None else []
        if with_healthcheck:
            other_changes.append(
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "valkey-cli validate",
                        "timeout_seconds": 30,
                        "interval_seconds": 15,
                    },
                    service=service,
                ),
            )

        for change in other_changes:
            change.service = service
        await DeploymentChange.objects.abulk_create(other_changes)

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        await service.arefresh_from_db()
        return project, service

    async def acreate_and_deploy_caddy_docker_service(
        self,
        with_healthcheck: bool = False,
        other_changes: list[DeploymentChange] | None = None,
    ):
        owner = await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project: Project = await Project.objects.aget(slug="zaneops", owner=owner)

        create_service_payload = {"slug": "caddy", "image": "caddy:2.8-alpine"}
        response = await self.async_client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service: Service = await Service.objects.aget(slug="caddy")

        service.network_alias = f"zn-{service.slug}-{service.unprefixed_id}"
        await service.asave()

        other_changes = other_changes if other_changes is not None else []
        if with_healthcheck:
            other_changes.append(
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                        "associated_port": 80,
                    },
                    service=service,
                ),
            )

        for change in other_changes:
            change.service = service
        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": await sync_to_async(URL.generate_default_domain)(
                            service
                        ),
                        "associated_port": 80,
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
            ]
            + other_changes
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        await service.arefresh_from_db()
        return project, service

    def create_and_deploy_caddy_docker_service(
        self,
        with_healthcheck: bool = False,
        other_changes: list[DeploymentChange] | None = None,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = Project.objects.get(slug="zaneops")
        create_service_payload = {"slug": "caddy", "image": "caddy:2.8-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug="caddy")

        service.network_alias = f"{service.slug}-{service.unprefixed_id}"
        service.save()

        other_changes = other_changes if other_changes is not None else []
        if with_healthcheck:
            other_changes.append(
                DeploymentChange(
                    field=DeploymentChange.ChangeField.HEALTHCHECK,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "PATH",
                        "value": "/",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                        "associated_port": 80,
                    },
                    service=service,
                ),
            )

        for change in other_changes:
            change.service = service
        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "caddy-web-server.fkiss.me",
                        "associated_port": 80,
                        "base_path": "/",
                        "strip_prefix": True,
                    },
                    service=service,
                ),
            ]
            + other_changes
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        return project, service

    def create_caddy_docker_service(self, slug="caddy"):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = Project.objects.get(slug="zaneops")
        create_service_payload = {"slug": "caddy", "image": "caddy:2.8-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug=slug)
        return project, service

    def create_redis_docker_service(self, slug="redis"):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = Project.objects.get(slug="zaneops")
        create_service_payload = {"slug": "redis", "image": "valkey/valkey:7.2-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug=slug)
        return project, service

    def create_git_service(
        self,
        slug="docs",
        repository="https://github.com/zane-ops/docs",
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = Project.objects.get(slug="zaneops")
        create_service_payload = {
            "slug": "docs",
            "repository_url": repository,
            "branch_name": "main",
        }
        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug=slug)
        return project, service

    async def acreate_and_deploy_git_service(
        self,
        slug="docs",
        repository="https://github.com/zaneops/docs",
        dockerfile: Optional[str] = None,
    ):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = await Project.objects.aget(slug="zaneops")
        create_service_payload = {
            "slug": "docs",
            "repository_url": repository,
            "branch_name": "main",
        }
        if dockerfile is not None:
            create_service_payload["dockerfile_path"] = dockerfile

        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = await Service.objects.aget(slug=slug)

        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        await service.arefresh_from_db()
        return project, service

    def create_and_deploy_git_service(
        self,
        slug="docs",
        repository="https://github.com/zaneops/docs",
        dockerfile: Optional[str] = None,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = Project.objects.get(slug="zaneops")
        create_service_payload = {
            "slug": "docs",
            "repository_url": repository,
            "branch_name": "main",
        }
        if dockerfile is not None:
            create_service_payload["dockerfile_path"] = dockerfile

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug=slug)

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        return project, service

    async def acreate_redis_docker_service(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops", "env_slug": "production"},
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
        )

        project = await Project.objects.aget(slug="zaneops")
        create_service_payload = {"slug": "redis", "image": "valkey/valkey:7.2-alpine"}
        response = await self.async_client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = await Service.objects.aget(slug="redis")
        return project, service


@dataclass
class FakeGitAuthor:
    name: str
    email: str


@dataclass
class FakeGitCommit:
    binsha: bytes
    message: str
    author: FakeGitAuthor


class FakeGit:
    NON_EXISTENT_REPOSITORY = "https://github.com/user/non-existent"
    DELETED_REPOSITORY = "https://github.com/user/deleted"
    NON_EXISTENT_BRANCH = "feat/non-existent"
    INVALID_COMMIT_SHA = "invalid"

    def checkout(self, commit_sha: str):
        if commit_sha == FakeGit.INVALID_COMMIT_SHA:
            raise GitCommandError("git checkout", status="invalid commit sha")
        self.commit_sha: Optional[str] = commit_sha

    def ls_remote(self, arg: Any, url: str, branch: Optional[str] = None):
        if url == self.NON_EXISTENT_REPOSITORY or branch == self.NON_EXISTENT_BRANCH:
            return ""
        else:
            return "6245e83dc119559b636a698dd76285b2b53f3fa5\trefs/heads/main\n"

    def clone_from(self, url: str, to_path: str, branch: str, *args, **kwargs):
        if url is None:
            raise GitCommandError("git clone", status="Cannot clone `None` repository.")
        if url == FakeGit.DELETED_REPOSITORY:
            raise GitCommandError("git clone", status="repository does not exist.")
        return FakeGit.FakeRepo(url, to_path, branch, git=self)

    class FakeRepo:

        def __init__(self, url: str, dest_path: str, branch: str, git: "FakeGit"):
            self.url = url
            self.dest_path = dest_path
            self.branch = branch
            self.git = git

        def commit(self, rev: str):
            return FakeGitCommit(
                binsha=rev.encode("utf-8"),
                message="Commit message",
                author=FakeGitAuthor(name="Fred Kiss", email="hello@gamil.com"),
            )


class FakeDockerClient:
    @dataclass
    class FakeNetwork:
        name: str
        id: str
        parent: "FakeDockerClient"
        labels: dict

        def remove(self):
            self.parent.network_remove(self.name)

    @dataclass
    class FakeImage:
        tags: set[str]
        id: str
        parent: "FakeDockerClient"
        labels: dict[str, str]

        def tag(self, repository: str, tag: str, *args, **kwargs):
            image = f"{repository}:{tag}"
            self.tags.add(image)
            self.parent.pulled_images.add(image)

        def remove(self):
            self.parent.remove_image(self.id)

    class FakeVolume:
        def __init__(
            self, parent: "FakeDockerClient", name: str, labels: dict | None = None
        ):
            self.name = name
            self.parent = parent
            self.labels = labels if labels is not None else {}

        def remove(self, force: bool):
            self.parent.volume_map.pop(self.name)

    class FakeConfig:
        def __init__(
            self, parent: "FakeDockerClient", name: str, labels: dict | None = None
        ):
            self.name = name
            self.id = name
            self.parent = parent
            self.labels = labels if labels is not None else {}

        def remove(self):
            self.parent.config_map.pop(self.name)

    class FakeService:
        def __init__(
            self,
            parent: "FakeDockerClient",
            name: str,
            volumes: dict[str, dict[str, str]] | None = None,
            configs: list[ConfigReference] | None = None,
            env: dict[str, str] | None = None,
            endpoint: EndpointSpec | None = None,
            resources: Resources | None = None,
            networks: List[NetworkAttachmentConfig] | None = None,
        ):
            self.attrs = {
                "Spec": {
                    "TaskTemplate": {
                        "Networks": [],
                    },
                }
            }
            self.name = name
            self.parent = parent
            self.attached_volumes = {} if volumes is None else volumes
            self.configs = [] if configs is None else configs
            self.env = {} if env is None else env
            self.endpoint = endpoint
            self.resources = resources
            self.id = name
            self.networks = networks or []
            self.swarm_tasks = [
                {
                    "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                    "Version": {"Index": 15078},
                    "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                    "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                    "Status": {
                        "Timestamp": "2024-04-25T20:11:42.770670997Z",
                        "State": "running",
                        "Message": "started",
                        # "Err": "task: non-zero exit (127)",
                        "ContainerStatus": {
                            "ContainerID": "abcd",
                            "ExitCode": 0,
                        },
                    },
                    "DesiredState": "running",
                    "NetworksAttachments": [{"Network": {"Spec": {"Name": "zane"}}}],
                }
            ]

        def remove(self):
            self.parent.services_remove(self.name)

        def update(self, **kwargs):
            if "networks" in kwargs:
                self.attrs["Spec"]["TaskTemplate"]["Networks"] = [
                    {"Target": network} for network in kwargs["networks"]
                ]
            if kwargs.get("mode") == {"Replicated": {"Replicas": 0}}:
                self.swarm_tasks = []

        def tasks(self, *args, **kwargs):
            return self.swarm_tasks

        def scale(self, replicas: int):
            """do nothing for now"""
            if replicas == 0:
                self.swarm_tasks = []

        def get_attached_volume(self, volume: Volume):
            return self.attached_volumes.get(get_volume_resource_name(volume.id))

        def get_attached_config(self, config: Config):
            return find_item_in_list(
                lambda c: c["ConfigID"]
                == get_config_resource_name(config.id, config.version),
                self.configs,
            )

    class FakeContainer:
        def __init__(self):
            self.status = "running"

        def stats(self, *args, **kwargs):
            # these are example stats
            return {
                "read": "2025-02-14T23:06:16.118896814Z",
                "preread": "2025-02-14T23:06:15.097411283Z",
                "pids_stats": {"current": 41, "limit": 18446744073709552000},
                "blkio_stats": {
                    "io_service_bytes_recursive": [
                        {"major": 254, "minor": 16, "op": "read", "value": 252493824},
                        {"major": 254, "minor": 16, "op": "write", "value": 1417216},
                        {"major": 253, "minor": 0, "op": "read", "value": 4096},
                        {"major": 253, "minor": 0, "op": "write", "value": 0},
                    ],
                    "io_serviced_recursive": None,
                    "io_queue_recursive": None,
                    "io_service_time_recursive": None,
                    "io_wait_time_recursive": None,
                    "io_merged_recursive": None,
                    "io_time_recursive": None,
                    "sectors_recursive": None,
                },
                "num_procs": 0,
                "storage_stats": {},
                "cpu_stats": {
                    "cpu_usage": {
                        "total_usage": 15337487000,
                        "usage_in_kernelmode": 2797673000,
                        "usage_in_usermode": 12539814000,
                    },
                    "system_cpu_usage": 6984884420000000,
                    "online_cpus": 12,
                    "throttling_data": {
                        "periods": 0,
                        "throttled_periods": 0,
                        "throttled_time": 0,
                    },
                },
                "precpu_stats": {
                    "cpu_usage": {
                        "total_usage": 15320380000,
                        "usage_in_kernelmode": 2795178000,
                        "usage_in_usermode": 12525202000,
                    },
                    "system_cpu_usage": 6984872330000000,
                    "online_cpus": 12,
                    "throttling_data": {
                        "periods": 0,
                        "throttled_periods": 0,
                        "throttled_time": 0,
                    },
                },
                "memory_stats": {
                    "usage": 234590208,
                    "stats": {
                        "active_anon": 172032,
                        "active_file": 22441984,
                        "anon": 151080960,
                        "anon_thp": 0,
                        "file": 82247680,
                        "file_dirty": 0,
                        "file_mapped": 57479168,
                        "file_writeback": 0,
                        "inactive_anon": 200667136,
                        "inactive_file": 11309056,
                        "kernel_stack": 0,
                        "pgactivate": 1258,
                        "pgdeactivate": 0,
                        "pgfault": 86109,
                        "pglazyfree": 0,
                        "pglazyfreed": 0,
                        "pgmajfault": 188,
                        "pgrefill": 26887,
                        "pgscan": 71638,
                        "pgsteal": 53917,
                        "shmem": 48496640,
                        "slab": 0,
                        "slab_reclaimable": 0,
                        "slab_unreclaimable": 0,
                        "sock": 0,
                        "thp_collapse_alloc": 0,
                        "thp_fault_alloc": 0,
                        "unevictable": 0,
                        "workingset_activate": 0,
                        "workingset_nodereclaim": 0,
                        "workingset_refault": 0,
                    },
                    "limit": 12591960064,
                },
                "name": "/srv-prj_nv2jCwsDQUV-srv_dkr_43jMSkbcuKX-dpl_dkr_Q9Y79C5SAsk.1.hl9nim19cq6antq2xz2v9aotf",
                "id": "0c5bcfcfda62d3ae48f397bbd25e54015dbf972cf0848514744ec88443ee3062",
                "networks": {
                    "eth0": {
                        "rx_bytes": 126,
                        "rx_packets": 3,
                        "rx_errors": 0,
                        "rx_dropped": 0,
                        "tx_bytes": 0,
                        "tx_packets": 0,
                        "tx_errors": 0,
                        "tx_dropped": 0,
                    },
                    "eth1": {
                        "rx_bytes": 4998,
                        "rx_packets": 119,
                        "rx_errors": 0,
                        "rx_dropped": 0,
                        "tx_bytes": 0,
                        "tx_packets": 0,
                        "tx_errors": 0,
                        "tx_dropped": 0,
                    },
                    "eth2": {
                        "rx_bytes": 1352,
                        "rx_packets": 20,
                        "rx_errors": 0,
                        "rx_dropped": 0,
                        "tx_bytes": 0,
                        "tx_packets": 0,
                        "tx_errors": 0,
                        "tx_dropped": 0,
                    },
                },
            }

        @staticmethod
        def exec_run(cmd: str, *args, **kwargs):
            if cmd == FakeDockerClient.FAILING_CMD:
                return 1, b"connection refused"
            return 0, b"connection succesful"

    PORT_USED_BY_HOST = 8080
    FAILING_CMD = "invalid"
    NONEXISTANT_IMAGE = "nonexistant"
    NONEXISTANT_PRIVATE_IMAGE = "example.com/nonexistant"
    GET_VOLUME_STORAGE_COMMAND = ""
    HOST_CPUS = 4
    HOST_MEMORY_IN_BYTES = 8 * 1024 * 1024 * 1024  # 8gb
    BAD_DOCKERFILE = "bad.Dockerfile"

    def __init__(self):
        self.volumes = MagicMock()
        self.configs = MagicMock()
        self.services = MagicMock()
        self.images = MagicMock()
        self.containers = MagicMock()
        self.api = MagicMock()
        self.is_logged_in = False
        self.credentials = {}
        self.image_map: dict[str, FakeDockerClient.FakeImage] = {}

        self.api.build = self.image_build

        self.images.search = self.images_search
        self.images.pull = self.images_pull
        self.images.get = self.images_get
        self.images.list = self.images_list
        self.images.get_registry_data = self.image_get_registry_data

        self.containers.run = self.containers_run
        self.containers.get = self.containers_get

        self.services.create = self.services_create
        self.services.get = self.services_get
        self.services.list = self.services_list

        self.volumes.create = self.volumes_create
        self.volumes.get = self.volumes_get
        self.volumes.list = self.volumes_list

        self.configs.list = self.config_list
        self.configs.create = self.config_create
        self.configs.get = self.config_get

        self.networks = MagicMock()
        self.network_map = {}  # type: dict[str, FakeDockerClient.FakeNetwork]

        self.networks.create = self.docker_create_network
        self.networks.get = self.docker_get_network
        self.networks.list = self.docker_network_list

        self.volume_map = {}  # type: dict[str, FakeDockerClient.FakeVolume]
        self.config_map = {}  # type: dict[str, FakeDockerClient.FakeConfig]
        self.service_map = {
            "proxy-service": FakeDockerClient.FakeService(
                name="zane_proxy", parent=self
            )
        }  # type: dict[str, FakeDockerClient.FakeService]
        self.pulled_images: set[str] = set()

    def remove_image(self, image_id: str):
        try:
            self.image_map.pop(image_id)
        except KeyError:
            pass

    def images_get(self, id: str):
        return self.image_map.get(id)

    def image_build(
        self,
        tag: str,
        dockerfile: str,
        labels: dict[str, str] | None = None,
        buildargs: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Generator[str, None, None]:
        if dockerfile.endswith(FakeDockerClient.BAD_DOCKERFILE):
            result = [
                {
                    "stream": f"{Colors.BLUE}Step 1/5 : FROM python:3.8-slim{Colors.ENDC}\n"
                },
                {"stream": f"{Colors.BLUE} ---> 123456789abc{Colors.ENDC}\n"},
                {"stream": f"{Colors.BLUE}Step 2/5 : WORKDIR /app{Colors.ENDC}\n"},
                {"stream": f"{Colors.BLUE} ---> Using cache{Colors.ENDC}\n"},
                {
                    "status": "Downloading",
                    "progress": "[====>         ] 12MB/40MB",
                    "id": "abcdef12345",
                },
                {"stream": f"{Colors.BLUE}Step 3/5 : COPY . /app{Colors.ENDC}\n"},
                {"stream": f"{Colors.BLUE} ---> 9f1b3c1d2e3f{Colors.ENDC}\n"},
                {
                    "status": "Installing",
                    "progressDetail": {"current": 50, "total": 100},
                    "id": "pip",
                },
                {
                    "errorDetail": {
                        "message": "COPY failed: no such file or directory"
                    },
                    "error": f"{Colors.RED}COPY failed: no such file or directory{Colors.ENDC}\n",
                },
            ]
        else:
            image_id = "sha256:7e2f3b8d5a4c"
            result = [
                {
                    "stream": f"{Colors.BLUE}Step 1/5 : FROM python:3.8-slim{Colors.ENDC}\n"
                },
                {"stream": f"{Colors.BLUE} ---> 123456789abc{Colors.ENDC}\n"},
                {"stream": f"{Colors.BLUE}Step 2/5 : WORKDIR /app{Colors.ENDC}\n"},
                {"stream": f"{Colors.BLUE} ---> Using cache{Colors.ENDC}\n"},
                {
                    "status": "Downloading",
                    "progress": "[====>         ] 12MB/40MB",
                    "id": "abcdef12345",
                },
                {"stream": f"{Colors.BLUE}Step 3/5 : COPY . /app{Colors.ENDC}\n"},
                {"stream": f"{Colors.BLUE} ---> 9f1b3c1d2e3f{Colors.ENDC}\n"},
                {
                    "status": "Installing",
                    "progressDetail": {"current": 50, "total": 100},
                    "id": "pip",
                },
                {
                    "stream": f"{Colors.BLUE} ---> Running in 4d3f9b8a7c6d{Colors.ENDC}\n"
                },
                {
                    "stream": f'{Colors.BLUE}Step 4/5 : CMD ["python", "app.py"]{Colors.ENDC}\n'
                },
                {"aux": {"ID": image_id}},
            ]
            self.image_map[image_id] = FakeDockerClient.FakeImage(
                id=image_id, labels=labels or {}, tags={tag}, parent=self
            )
            self.pulled_images.add(tag)

        for data in result:
            yield json.dumps(data)

    def get_deployment_service(self, deployment: Deployment):
        return self.service_map.get(
            get_swarm_service_name_for_deployment(
                deployment_hash=deployment.hash,
                service_id=deployment.service_id,  # type: ignore
                project_id=deployment.service.project_id,  # type: ignore
            )
        )

    def services_list(self, **kwargs):
        if kwargs.get("filter") == {"label": "zane.role=proxy"}:
            return [self.service_map["proxy_service"]]
        return [service for service in self.service_map.values()]

    @staticmethod
    def events(decode: bool, filters: dict):
        return []

    @staticmethod
    def containers_get(container_id: str):
        return FakeDockerClient.FakeContainer()

    def containers_run(self, command: str, *args, **kwargs):
        ports: dict[str, tuple[str, int]] = kwargs.get("ports")  # type: ignore
        if ports is not None:
            _, port = list(ports.values())[0]
            if port == self.PORT_USED_BY_HOST:
                raise docker.errors.APIError(f"Port {port} is already used")
        if command == SERVER_RESOURCE_LIMIT_COMMAND:
            return f"{self.HOST_CPUS}\n{self.HOST_MEMORY_IN_BYTES}\n".encode("utf-8")

    def volumes_create(self, name: str, labels: dict, **kwargs):
        self.volume_map[name] = FakeDockerClient.FakeVolume(
            parent=self, name=name, labels=labels
        )

    def config_create(self, name: str, labels: dict, **kwargs):
        self.config_map[name] = FakeDockerClient.FakeConfig(
            parent=self,
            name=name,
            labels=labels,
        )

    def config_get(self, name: str):
        if name not in self.config_map:
            raise docker.errors.NotFound("Config Not found")
        return self.config_map[name]

    def config_list(self, filters: dict):
        label_in_filters: list[str] = filters.get("label", [])
        labels = {}
        for label in label_in_filters:
            key, value = label.split("=")
            labels[key] = value
        return [
            config for config in self.config_map.values() if config.labels == labels
        ]

    def volumes_get(self, name: str):
        if name not in self.volume_map:
            raise docker.errors.NotFound("Volume Not found")
        return self.volume_map[name]

    def volumes_list(self, filters: dict):
        label_in_filters: list[str] = filters.get("label", [])
        labels: dict[str, str] = {}
        for label in label_in_filters:
            key, value = label.split("=")
            labels[key] = value
        return [
            volume
            for volume in self.volume_map.values()
            if labels.items() <= volume.labels.items()
        ]

    def images_list(self, filters: dict):
        label_in_filters: list[str] = filters.get("label", [])
        labels: dict[str, str] = {}
        for label in label_in_filters:
            key, value = label.split("=")
            labels[key] = value
        return [
            image
            for image in self.image_map.values()
            if labels.items() <= image.labels.items()
        ]

    def services_get(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound(f"Service with `{name=}` Not found")
        return self.service_map[name]

    def services_remove(self, name: str):
        if name not in self.service_map:
            raise docker.errors.NotFound("Service Not found")
        self.service_map.pop(name)

    def services_create(
        self,
        name: str,
        *args,
        **kwargs,
    ):
        image: str | None = kwargs.get("image", None)
        mounts: list[str] = kwargs.get("mounts", [])
        env: list[str] = kwargs.get("env", [])
        endpoint_spec = kwargs.get("endpoint_spec", None)
        resources = kwargs.get("resources", None)
        if image not in self.pulled_images:
            raise docker.errors.NotFound("image not pulled")
        volumes: dict[str, dict[str, str]] = {}
        for mount in mounts:
            volume_name, mount_path, mode = mount.split(":")
            if not volume_name.startswith("/") and volume_name not in self.volume_map:
                raise docker.errors.NotFound("Volume not created")
            volumes[volume_name] = {
                "mount_path": mount_path,
                "mode": mode,
            }

        envs: dict[str, str] = {}
        for var in env:
            key, value = var.split("=")
            envs[key] = value

        self.service_map[name] = FakeDockerClient.FakeService(
            parent=self,
            name=name,
            volumes=volumes,
            env=envs,
            endpoint=endpoint_spec,
            resources=resources,
            networks=kwargs.get("networks", []),
            configs=kwargs.get("configs", []),
        )

    def login(self, username: str, password: str, registry: str, **kwargs):
        if username != "fredkiss3" or password != "s3cret":
            raise docker.errors.APIError("Bad Credentials")
        self.credentials = dict(username=username, password=password)
        self.is_logged_in = True

    @staticmethod
    def images_search(term: str, limit: int) -> List[DockerImageResultFromRegistry]:
        return [
            {
                "name": "caddy",
                "is_official": True,
                "is_automated": True,
                "description": "Caddy 2 is a powerful, enterprise-ready,"
                " open source web server with automatic HTTPS written in Go",
            },
            {
                "description": "caddy webserver optimized for usage within the SIWECOS project",
                "is_automated": False,
                "is_official": False,
                "name": "siwecos/caddy",
            },
        ]

    def images_pull(self, repository: str, *args, **kwargs):
        if repository == self.NONEXISTANT_IMAGE:
            raise docker.errors.ImageNotFound(
                f"The image `{repository}` does not exists."
            )
        self.pulled_images.add(repository)

    def image_get_registry_data(self, image: str, auth_config: dict):
        if auth_config is not None:
            username, password = auth_config["username"], auth_config["password"]
            if (username != "fredkiss3" or password != "s3cret") and (
                username != "" or password != ""
            ):
                raise docker.errors.APIError("Invalid credentials")

            if image == self.NONEXISTANT_PRIVATE_IMAGE:
                raise docker.errors.NotFound(
                    "This image does not exist in the registry"
                )
            self.is_logged_in = True
        else:
            if image == self.NONEXISTANT_IMAGE:
                raise docker.errors.ImageNotFound("This image does not exist")

    def docker_create_network(self, name: str, labels: dict, **kwargs):
        created_network = FakeDockerClient.FakeNetwork(
            name=name, id=name, parent=self, labels=labels
        )
        self.network_map[name] = created_network
        return created_network

    def docker_get_network(self, name: str):
        network = self.network_map.get(name)

        if network is None:
            raise docker.errors.NotFound("network not found")
        return network

    def docker_network_list(self, filters: dict):
        label_in_filters: list[str] = filters.get("label", [])
        labels = {}
        for label in label_in_filters:
            key, value = label.split("=")
            labels[key] = value

        return [
            net
            for net in self.network_map.values()
            if labels.items() <= net.labels.items()
        ]

    def network_remove(self, name: str):
        network = self.network_map.pop(name)
        if network is None:
            raise docker.errors.NotFound("network not found")

    def get_project_network(self, p: Project):
        return self.network_map.get(get_network_resource_name(p.id))

    def get_project_networks(self, p: Project):
        return [
            net
            for net in self.network_map.values()
            if net.labels.get("zane-project") == p.id
        ]

    def get_env_network(self, env: Environment):
        return self.network_map.get(
            get_env_network_resource_name(env.id, env.project_id)  # type: ignore
        )

    def get_networks(self):
        return self.network_map
