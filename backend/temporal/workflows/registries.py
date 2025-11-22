import asyncio
from datetime import timedelta
from typing import cast
from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        create_build_registry_swarm_service,
        create_docker_configs_for_registry,
        create_docker_volume_for_registry,
        pull_registry_image,
        cleanup_docker_registry_service_resources,
        remove_service_registry_url,
        add_swarm_service_registry_service_url,
    )

from ..shared import (
    DeployRegistryPayload,
    CreateSwarmRegistryServiceDetails,
    DeleteSwarmRegistryServiceDetails,
)


@workflow.defn(name="destroy-build-registry")
class DestroyBuildRegistryWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: DeleteSwarmRegistryServiceDetails):
        await asyncio.gather(
            workflow.execute_activity(
                remove_service_registry_url,
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            ),
            workflow.execute_activity(
                cleanup_docker_registry_service_resources,
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            ),
        )


@workflow.defn(name="deploy-build-registry")
class DeployBuildRegistryWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, registry: DeployRegistryPayload):
        volume, config_data = await asyncio.gather(
            workflow.execute_activity(
                create_docker_volume_for_registry,
                registry,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            ),
            workflow.execute_activity(
                create_docker_configs_for_registry,
                registry,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            ),
        )

        await workflow.execute_activity(
            pull_registry_image,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        swarm_details = CreateSwarmRegistryServiceDetails(
            registry=registry,
            configs={cast(str, config.id): config for config in config_data.configs},
            volume=volume,
            alias=registry.service_alias,
            swarm_id=registry.swarm_service_name,
        )

        await workflow.execute_activity(
            create_build_registry_swarm_service,
            swarm_details,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity(
            add_swarm_service_registry_service_url,
            registry,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )
