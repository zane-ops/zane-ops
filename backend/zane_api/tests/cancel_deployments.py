# type: ignore
from .base import AuthAPITestCase
from unittest.mock import MagicMock, call
import asyncio
from datetime import timedelta
from temporalio.common import RetryPolicy
from asgiref.sync import sync_to_async
from ..serializers import ServiceSerializer, URLModelSerializer
from ..temporal.activities import get_swarm_service_name_for_deployment, ZaneProxyClient
from ..temporal import (
    DeploymentDetails,
    DockerDeploymentStep,
    DeployDockerServiceWorkflow,
    DeployServiceWorkflowResult,
    CancelDeploymentSignalInput,
)
from ..models import (
    Deployment,
    DeploymentChange,
    Volume,
    URL,
    DeploymentURL,
)
from ..dtos import URLDto
from django.conf import settings
from rest_framework import status
from django.urls import reverse
import requests
import os
import unittest


# @unittest.skipIf(os.environ.get("CI") == "true", "Skipped in CI")
class DockerServiceDeploymentCancelTests(AuthAPITestCase):
    async def test_cancel_deployment_at_initial_step(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_redis_docker_service()
                service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                new_deployment: Deployment = await Deployment.objects.acreate(
                    service_snapshot=service_snapshot,
                    service=service,
                )

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.INITIALIZED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )
                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                self.assertIsNone(
                    self.fake_docker_client.get_deployment_service(new_deployment)
                )

    async def test_cancel_deployment_at_volume_created_step(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_redis_docker_service()

                new_deployment = await Deployment.objects.acreate(
                    service=service,
                )
                await DeploymentChange.objects.acreate(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                    service=service,
                    deployment=new_deployment,
                )

                await sync_to_async(service.apply_pending_changes)(new_deployment)
                new_deployment.service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                await new_deployment.asave()

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.VOLUMES_CREATED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                docker_deployment = self.fake_docker_client.get_deployment_service(
                    new_deployment
                )
                self.assertIsNone(docker_deployment)
                self.assertEqual(0, len(self.fake_docker_client.volume_map))

    async def test_cancel_deployment_at_config_created_step(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_redis_docker_service()

                new_deployment = await Deployment.objects.acreate(
                    service=service,
                )
                await DeploymentChange.objects.acreate(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value=dict(
                        mount_path="/etc/caddy/Caddyfile",
                        contents="""
                    :80 {
                        respond "hello from caddy"
                    }
                    """,
                        name="caddyfile",
                        language="plaintext",
                    ),
                    service=service,
                    deployment=new_deployment,
                )

                await sync_to_async(service.apply_pending_changes)(new_deployment)
                new_deployment.service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                await new_deployment.asave()

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.CONFIGS_CREATED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                docker_deployment = self.fake_docker_client.get_deployment_service(
                    new_deployment
                )
                self.assertIsNone(docker_deployment)
                self.assertEqual(0, len(self.fake_docker_client.config_map))

    async def test_cancel_deployment_at_service_scaled_down(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_redis_docker_service(
                    other_changes=[
                        DeploymentChange(
                            field=DeploymentChange.ChangeField.PORTS,
                            type=DeploymentChange.ChangeType.ADD,
                            new_value={
                                "host": 6739,
                                "forwarded": 6739,
                            },
                        )
                    ]
                )

                production_deployment = await service.alatest_production_deployment

                new_deployment = await Deployment.objects.acreate(
                    service=service,
                    service_snapshot=await sync_to_async(
                        lambda: ServiceSerializer(service).data
                    )(),
                )

                fake_service = MagicMock()
                fake_service.tasks.side_effect = lambda *args, **kwargs: []
                fake_service_list = MagicMock()
                fake_service_list.get.return_value = fake_service
                self.fake_docker_client.services = fake_service_list

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                docker_deployment = self.fake_docker_client.get_deployment_service(
                    new_deployment
                )
                self.assertIsNone(docker_deployment)

                fake_service_list.get.assert_has_calls(
                    [
                        call(
                            get_swarm_service_name_for_deployment(
                                deployment_hash=production_deployment.hash,
                                service_id=production_deployment.service_id,
                                project_id=production_deployment.service.project_id,
                            )
                        )
                    ],
                    any_order=True,
                )
                fake_service.update.assert_called()
                scaled_up = any(
                    call.kwargs.get("mode") == {"Replicated": {"Replicas": 1}}
                    for call in fake_service.update.call_args_list
                )
                self.assertTrue(scaled_up)

    async def test_cancel_deployment_at_swarm_service_created(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_redis_docker_service()

                new_deployment = await Deployment.objects.acreate(
                    service=service,
                    service_snapshot=await sync_to_async(
                        lambda: ServiceSerializer(service).data
                    )(),
                )

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.SWARM_SERVICE_CREATED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )
                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                docker_deployment = self.fake_docker_client.get_deployment_service(
                    new_deployment
                )
                self.assertIsNone(docker_deployment)

    async def test_cancel_deployment_at_deployment_exposed_to_http(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_caddy_docker_service()

                new_deployment: Deployment = await Deployment.objects.acreate(
                    service=service,
                    service_snapshot=await sync_to_async(
                        lambda: ServiceSerializer(service).data
                    )(),
                )
                await sync_to_async(DeploymentURL.generate_for_deployment)(
                    new_deployment, 80, service
                )
                await new_deployment.asave()

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                docker_deployment = self.fake_docker_client.get_deployment_service(
                    new_deployment
                )
                self.assertIsNone(docker_deployment)
                response = requests.get(
                    ZaneProxyClient.get_uri_for_deployment(
                        new_deployment.hash, (await new_deployment.urls.afirst()).domain
                    )
                )
                self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    async def test_cancel_deployment_at_service_exposed_to_http(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_caddy_docker_service()
                url_to_update: URL = await service.urls.afirst()
                updated_url = URLDto(
                    domain=f"caddy.{settings.ROOT_DOMAIN}",
                    base_path="/",
                    strip_prefix=True,
                )
                url_to_add = URLDto(
                    domain="web-server.fred.kiss", base_path="/", strip_prefix=True
                )

                new_deployment = await Deployment.objects.acreate(
                    service=service,
                )
                await DeploymentChange.objects.abulk_create(
                    [
                        DeploymentChange(
                            field=DeploymentChange.ChangeField.URLS,
                            type=DeploymentChange.ChangeType.ADD,
                            new_value=dict(
                                domain=url_to_add.domain,
                                base_path=url_to_add.base_path,
                                strip_prefix=url_to_add.strip_prefix,
                            ),
                            service=service,
                        ),
                        DeploymentChange(
                            field=DeploymentChange.ChangeField.URLS,
                            type=DeploymentChange.ChangeType.UPDATE,
                            item_id=url_to_update.id,
                            old_value=URLModelSerializer(url_to_update).data,
                            new_value=dict(
                                domain=updated_url.domain,
                                base_path=updated_url.base_path,
                                strip_prefix=updated_url.strip_prefix,
                            ),
                            service=service,
                        ),
                    ]
                )

                await sync_to_async(service.apply_pending_changes)(new_deployment)
                new_deployment.service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                await new_deployment.asave()

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.SERVICE_EXPOSED_TO_HTTP,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.CANCELLED,
                    workflow_result.deployment_status,
                )
                self.assertIsNone(workflow_result.healthcheck_result)
                docker_deployment = self.fake_docker_client.get_deployment_service(
                    new_deployment
                )
                self.assertIsNone(docker_deployment)

                response = requests.get(
                    ZaneProxyClient.get_uri_for_service_url(service.id, url_to_add)
                )
                self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

                response = requests.get(
                    ZaneProxyClient.get_uri_for_service_url(service.id, updated_url)
                )
                self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

                response = requests.get(
                    ZaneProxyClient.get_uri_for_service_url(service.id, url_to_update)
                )
                self.assertEqual(status.HTTP_200_OK, response.status_code)

    async def test_cancel_already_finished_do_nothing(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                owner = await self.aLoginUser()
                p, service = await self.acreate_and_deploy_redis_docker_service()
                service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                new_deployment = await Deployment.objects.acreate(
                    service_snapshot=service_snapshot,
                    service=service,
                )

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=DockerDeploymentStep.FINISHED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,
                    ),
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
                )

                # Create task for the workflow result
                workflow_result_task = asyncio.create_task(workflow_handle.result())

                # Send signal concurrently
                await workflow_handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    arg=CancelDeploymentSignalInput(
                        deployment_hash=new_deployment.hash
                    ),
                    rpc_timeout=timedelta(seconds=5),
                )

                # Wait for the workflow result to complete
                workflow_result: DeployServiceWorkflowResult = (
                    await workflow_result_task
                )

                self.assertEqual(
                    Deployment.DeploymentStatus.HEALTHY,
                    workflow_result.deployment_status,
                )
                self.assertIsNotNone(workflow_result.healthcheck_result)
                self.assertIsNotNone(
                    self.fake_docker_client.get_deployment_service(new_deployment)
                )


class DockerServiceCancelDeploymentViewTests(AuthAPITestCase):
    @unittest.skipIf(os.environ.get("CI") == "true", "Skipped in CI")
    async def test_cancel_deployment_simple(self):
        async with self.workflowEnvironment() as env:
            # with env.auto_time_skipping_disabled():
            owner = await self.aLoginUser()
            p, service = await self.acreate_and_deploy_redis_docker_service()

            new_deployment = await Deployment.objects.acreate(
                service=service,
                service_snapshot=await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )(),
            )

            payload = await DeploymentDetails.afrom_deployment(
                deployment=new_deployment,
                pause_at_step=DockerDeploymentStep.SWARM_SERVICE_CREATED,
            )

            workflow_handle = await env.client.start_workflow(
                workflow=DeployDockerServiceWorkflow.run,
                arg=payload,
                id=payload.workflow_id,
                retry_policy=RetryPolicy(
                    maximum_attempts=1,
                ),
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )

            # Send signal concurrently
            [workflow_result, response] = await asyncio.gather(
                workflow_handle.result(),
                self.async_client.put(
                    reverse(
                        "zane_api:services.cancel_deployment",
                        kwargs={
                            "project_slug": p.slug,
                            "env_slug": "production",
                            "service_slug": service.slug,
                            "deployment_hash": new_deployment.hash,
                        },
                    ),
                ),
            )

            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertEqual(
                Deployment.DeploymentStatus.CANCELLED,
                workflow_result.deployment_status,
            )
            self.assertIsNone(workflow_result.healthcheck_result)
            await new_deployment.arefresh_from_db()
            self.assertEqual(
                Deployment.DeploymentStatus.CANCELLED, new_deployment.status
            )
            self.assertIsNotNone(new_deployment.status_reason)

    async def test_cancel_not_started_deployment_set_status_to_cancelled(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        new_deployment: Deployment = await Deployment.objects.acreate(service=service)
        new_deployment.service_snapshot = await sync_to_async(
            lambda: ServiceSerializer(service).data
        )()
        await new_deployment.asave()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.cancel_deployment",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": new_deployment.hash,
                },
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        await new_deployment.arefresh_from_db()
        self.assertEqual(Deployment.DeploymentStatus.CANCELLED, new_deployment.status)
        self.assertIsNotNone(new_deployment.status_reason)

    async def test_cannot_cancel_non_cancelleable_deployment(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        new_deployment: Deployment = await Deployment.objects.acreate(
            service=service, status=Deployment.DeploymentStatus.REMOVED
        )
        new_deployment.service_snapshot = await sync_to_async(
            lambda: ServiceSerializer(service).data
        )()
        await new_deployment.asave()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.cancel_deployment",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": new_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    async def test_cannot_cancel_already_finished_deployment(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        deployment_hash = response.json().get("hash")
        new_deployment: Deployment = (
            await Deployment.objects.filter(hash=deployment_hash)
            .select_related("service")
            .afirst()
        )

        response = await self.async_client.put(
            reverse(
                "zane_api:services.cancel_deployment",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": new_deployment.hash,
                },
            ),
        )

        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
