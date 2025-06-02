# type: ignore
from .base import AuthAPITestCase
from unittest.mock import MagicMock, call
import asyncio
from datetime import timedelta
from temporalio.common import RetryPolicy
from asgiref.sync import sync_to_async
from ..serializers import ServiceSerializer, URLModelSerializer
from temporal.activities import (
    get_swarm_service_name_for_deployment,
    ZaneProxyClient,
)
from temporal.shared import (
    DeploymentDetails,
    DeployServiceWorkflowResult,
    CancelDeploymentSignalInput,
)
from temporal.workflows import (
    DockerDeploymentStep,
    GitDeploymentStep,
    DeployDockerServiceWorkflow,
    DeployGitServiceWorkflow,
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
from ..utils import jprint


class GitServiceDeploymentCancelTests(AuthAPITestCase):
    async def test_cancel_deployment_at_git_clone(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                p, service = await self.acreate_and_deploy_git_service()
                service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                new_deployment: Deployment = await Deployment.objects.acreate(
                    service_snapshot=service_snapshot,
                    commit_message="-",
                    commit_sha="1234abcd",
                    service=service,
                )

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=GitDeploymentStep.CLONING_REPOSITORY,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
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
                    DeployGitServiceWorkflow.cancel_deployment,
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

    async def test_cancel_deployment_at_git_repository_cloned(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                p, service = await self.acreate_and_deploy_git_service()
                service_snapshot = await sync_to_async(
                    lambda: ServiceSerializer(service).data
                )()
                new_deployment: Deployment = await Deployment.objects.acreate(
                    service_snapshot=service_snapshot,
                    commit_message="-",
                    commit_sha="1234abcd",
                    service=service,
                )

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=GitDeploymentStep.REPOSITORY_CLONED,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
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
                    DeployGitServiceWorkflow.cancel_deployment,
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

    async def test_cancel_deployment_at_building_image(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                p, service = await self.acreate_git_service()
                new_deployment: Deployment = await Deployment.objects.acreate(
                    commit_message="-",
                    commit_sha="1234abcd",
                    service=service,
                )

                def get_service_snapshot(new_deployment: Deployment):
                    service.apply_pending_changes(new_deployment)
                    return ServiceSerializer(service).data

                service_snapshot = await sync_to_async(get_service_snapshot)(
                    new_deployment
                )
                new_deployment.service_snapshot = service_snapshot
                await new_deployment.asave()

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=GitDeploymentStep.BUILDING_IMAGE,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
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
                    DeployGitServiceWorkflow.cancel_deployment,
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

    async def test_cancel_deployment_at_image_built(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                p, service = await self.acreate_git_service()
                new_deployment: Deployment = await Deployment.objects.acreate(
                    commit_message="-",
                    commit_sha="1234abcd",
                    service=service,
                )

                def get_service_snapshot(new_deployment: Deployment):
                    service.apply_pending_changes(new_deployment)
                    return ServiceSerializer(service).data

                service_snapshot = await sync_to_async(get_service_snapshot)(
                    new_deployment
                )
                new_deployment.service_snapshot = service_snapshot
                await new_deployment.asave()

                payload = await DeploymentDetails.afrom_deployment(
                    deployment=new_deployment,
                    pause_at_step=GitDeploymentStep.IMAGE_BUILT,
                )

                workflow_handle = await env.client.start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
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
                    DeployGitServiceWorkflow.cancel_deployment,
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


class DockerServiceDeploymentCancelTests(AuthAPITestCase):
    async def test_cancel_deployment_at_initial_step(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
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
                p, service = await self.acreate_and_deploy_caddy_docker_service()
                first_deployment: Deployment = await service.deployments.afirst()

                new_deployment: Deployment = await Deployment.objects.acreate(
                    service=service,
                    service_snapshot=await sync_to_async(
                        lambda: ServiceSerializer(service).data
                    )(),
                    slot=Deployment.get_next_deployment_slot(first_deployment),
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
                    retry_policy=RetryPolicy(maximum_attempts=1),
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
                _, service = await self.acreate_and_deploy_caddy_docker_service()
                first_deployment: Deployment = await service.deployments.afirst()
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
                    slot=Deployment.get_next_deployment_slot(first_deployment),
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

    async def test_cancel_deployment_reset_the_network_alias_correctly_when_deploying(
        self,
    ):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
                _, service = await self.acreate_and_deploy_caddy_docker_service()
                first_deployment: Deployment = await service.deployments.afirst()
                url: URL = await service.urls.afirst()

                new_deployment = await Deployment.objects.acreate(
                    service=service,
                    slot=Deployment.get_next_deployment_slot(first_deployment),
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
                    ZaneProxyClient.get_uri_for_service_url(service.id, url)
                )
                data = response.json()
                jprint(response.json())
                self.assertEqual(status.HTTP_200_OK, response.status_code)
                upstream = data["handle"][0]["routes"][0]["handle"][-1]["upstreams"][0][
                    "dial"
                ].split(":")
                self.assertEqual(first_deployment.network_alias, upstream[0])

    async def test_cancel_already_finished_do_nothing(self):
        async with self.workflowEnvironment() as env:
            with env.auto_time_skipping_disabled():
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


@pytest.mark.django_db(transaction=True)
class TestWebhookDockerCancelPreviousDeployments(AuthAPITestCase):
    async def test_cancel_previous_true_workflow_started(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_workflow_id_old",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")  # Prevent new workflow

        url = reverse(
            "zane_api:deployments.webhook_docker_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": True, "new_image": "newimage:latest"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_called_once()
        
        # Check the arguments of the call
        args, kwargs = mock_workflow_signal.call_args
        assert kwargs["workflow"] == DeployDockerServiceWorkflow.run
        assert kwargs["signal"] == DeployDockerServiceWorkflow.cancel_deployment
        assert isinstance(kwargs["arg"], CancelDeploymentSignalInput)
        assert kwargs["arg"].deployment_hash == old_deployment.hash
        assert kwargs["workflow_id"] == old_deployment.workflow_id

        assert await Deployment.objects.filter(service=service).acount() == 2 # Old and new

    async def test_cancel_previous_true_workflow_not_started(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.QUEUED,
            workflow_id="fake_workflow_id_old_not_started",
            started_at=None, # Ensure it's None
        )
        
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_docker_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": True, "new_image": "anotherimage:latest"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        await old_deployment.arefresh_from_db()
        assert old_deployment.status == Deployment.DeploymentStatus.CANCELLED
        assert "Cancelled due to new deployment request." in old_deployment.status_reason
        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_false_workflow_started(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_workflow_id_old",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_docker_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": False, "new_image": "newimage:latest"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_not_called()
        await old_deployment.arefresh_from_db()
        assert old_deployment.status == Deployment.DeploymentStatus.STARTING # Unchanged
        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_true_no_active_deployments(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        # Previous deployment is in a non-active state
        await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.HEALTHY, 
            workflow_id="fake_workflow_id_healthy",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_docker_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": True, "new_image": "newimage:latest"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_not_called()
        assert await Deployment.objects.filter(service=service).acount() == 2
        # Ensure the new deployment is created with a pending status (or whatever start_workflow mock allows)
        assert await Deployment.objects.filter(service=service, status=Deployment.DeploymentStatus.QUEUED).acount() == 1


@pytest.mark.django_db(transaction=True)
class TestBulkDeployCancelPreviousDeployments(AuthAPITestCase):
    async def test_bulk_cancel_previous_true_mixed_services(self, mocker):
        project, environment = await self.acreate_project_and_environment()

        # Service 1: Docker, active deployment, workflow started
        service1 = await self.acreate_docker_service(project=project, environment=environment, slug_base="s1")
        old_depl1 = await Deployment.objects.acreate(
            service=service1, status=Deployment.DeploymentStatus.STARTING, workflow_id="wf1", started_at=timezone.now()
        )

        # Service 2: Git, active deployment, workflow NOT started
        service2 = await self.acreate_git_service(project=project, environment=environment, slug_base="s2")
        old_depl2 = await Deployment.objects.acreate(
            service=service2, status=Deployment.DeploymentStatus.QUEUED, workflow_id="wf2", started_at=None
        )

        # Service 3: Docker, no active deployment (e.g., previous one failed)
        service3 = await self.acreate_docker_service(project=project, environment=environment, slug_base="s3")
        await Deployment.objects.acreate(
            service=service3, status=Deployment.DeploymentStatus.FAILED, workflow_id="wf3_failed"
        )
        
        # Service 4: Git, healthy deployment (should not be cancelled)
        service4 = await self.acreate_git_service(project=project, environment=environment, slug_base="s4")
        await Deployment.objects.acreate(
            service=service4, status=Deployment.DeploymentStatus.HEALTHY, workflow_id="wf4_healthy", started_at=timezone.now()
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        # Mock start_workflow for all services to prevent actual new deployments
        mocker.patch("zane_api.views.deployments.start_workflow")


        url = reverse(
            "zane_api:deployments.bulk_deploy_services",
            kwargs={"project_slug": project.slug, "env_slug": environment.name},
        )
        payload = {
            "service_ids": [str(service1.id), str(service2.id), str(service3.id), str(service4.id)],
            "cancel_previous_deployments": True,
        }
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED

        # Assertions for Service 1 (Docker, workflow started)
        mock_workflow_signal.assert_any_call(
            workflow=DeployDockerServiceWorkflow.run,
            signal=DeployDockerServiceWorkflow.cancel_deployment,
            arg=CancelDeploymentSignalInput(deployment_hash=old_depl1.hash),
            workflow_id=old_depl1.workflow_id,
        )

        # Assertions for Service 2 (Git, workflow not started)
        await old_depl2.arefresh_from_db()
        assert old_depl2.status == Deployment.DeploymentStatus.CANCELLED
        assert "Cancelled due to new bulk deployment request." in old_depl2.status_reason
        
        # Assertions for Service 3 (New deployment created)
        assert await Deployment.objects.filter(service=service3, status=Deployment.DeploymentStatus.QUEUED).acount() == 1
        
        # Assertions for Service 4 (Healthy deployment, not cancelled, new one queued)
        s4_deployments = await sync_to_async(list)(Deployment.objects.filter(service=service4).order_by('created_at'))
        assert len(s4_deployments) == 2
        assert s4_deployments[0].status == Deployment.DeploymentStatus.HEALTHY # Original healthy one
        assert s4_deployments[1].status == Deployment.DeploymentStatus.QUEUED # New one

        # Verify new deployments were created for s1, s2, s3, s4
        assert await Deployment.objects.filter(service=service1, status=Deployment.DeploymentStatus.QUEUED).acount() == 1
        assert await Deployment.objects.filter(service=service2, status=Deployment.DeploymentStatus.QUEUED).acount() == 1
        # Total calls to workflow_signal should be 1 (only for service1)
        assert mock_workflow_signal.call_count == 1

    async def test_bulk_cancel_previous_false_active_deployments(self, mocker):
        project, environment = await self.acreate_project_and_environment()
        service1 = await self.acreate_docker_service(project=project, environment=environment, slug_base="s1")
        old_depl1 = await Deployment.objects.acreate(
            service=service1, status=Deployment.DeploymentStatus.STARTING, workflow_id="wf1_false", started_at=timezone.now()
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.bulk_deploy_services",
            kwargs={"project_slug": project.slug, "env_slug": environment.name},
        )
        payload = {
            "service_ids": [str(service1.id)],
            "cancel_previous_deployments": False,
        }
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_not_called()
        await old_depl1.arefresh_from_db()
        assert old_depl1.status == Deployment.DeploymentStatus.STARTING # Unchanged
        assert await Deployment.objects.filter(service=service1, status=Deployment.DeploymentStatus.QUEUED).acount() == 1



@pytest.mark.django_db(transaction=True)
class TestWebhookGitCancelPreviousDeployments(AuthAPITestCase):
    async def test_cancel_previous_true_workflow_started(self, mocker):
        project, service = await self.acreate_git_service_with_env() # Git specific
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_workflow_id_old_git",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_git_deploy", # Git specific URL
            kwargs={"deploy_token": service.deploy_token},
        )
        # Git webhook serializer expects ignore_build_cache and commit_sha
        payload = {"cancel_previous_deployments": True, "ignore_build_cache": False, "commit_sha": "newcommit"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_called_once()
        
        args, kwargs = mock_workflow_signal.call_args
        assert kwargs["workflow"] == DeployGitServiceWorkflow.run # Git specific workflow
        assert kwargs["signal"] == DeployGitServiceWorkflow.cancel_deployment # Git specific signal
        assert isinstance(kwargs["arg"], CancelDeploymentSignalInput)
        assert kwargs["arg"].deployment_hash == old_deployment.hash
        assert kwargs["workflow_id"] == old_deployment.workflow_id

        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_true_workflow_not_started(self, mocker):
        project, service = await self.acreate_git_service_with_env()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.QUEUED,
            workflow_id="fake_workflow_id_old_git_not_started",
            started_at=None,
        )
        
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_git_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": True, "ignore_build_cache": False, "commit_sha": "anothercommit"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        await old_deployment.arefresh_from_db()
        assert old_deployment.status == Deployment.DeploymentStatus.CANCELLED
        assert "Cancelled due to new deployment request." in old_deployment.status_reason
        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_false_workflow_started(self, mocker):
        project, service = await self.acreate_git_service_with_env()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_workflow_id_old_git",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_git_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": False, "ignore_build_cache": False, "commit_sha": "newcommitfalse"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_not_called()
        await old_deployment.arefresh_from_db()
        assert old_deployment.status == Deployment.DeploymentStatus.STARTING
        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_true_no_active_deployments(self, mocker):
        project, service = await self.acreate_git_service_with_env()
        await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.HEALTHY, 
            workflow_id="fake_workflow_id_healthy_git",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.deployments.workflow_signal")
        mocker.patch("zane_api.views.deployments.start_workflow")

        url = reverse(
            "zane_api:deployments.webhook_git_deploy",
            kwargs={"deploy_token": service.deploy_token},
        )
        payload = {"cancel_previous_deployments": True, "ignore_build_cache": False, "commit_sha": "newcommitnoactive"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow_signal.assert_not_called()
        assert await Deployment.objects.filter(service=service).acount() == 2
        assert await Deployment.objects.filter(service=service, status=Deployment.DeploymentStatus.QUEUED).acount() == 1
