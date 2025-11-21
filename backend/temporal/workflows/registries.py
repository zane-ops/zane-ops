import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        create_build_registry_swarm_service,
        create_docker_config_for_registry,
        create_docker_volume_for_registry,
        pull_registry_image,
        cleanup_docker_registry_service_resources,
        remove_service_registry_url,
    )

from ..shared import (
    RegistryDetails,
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
    async def run(self, registry: RegistryDetails):
        volume, config = await asyncio.gather(
            workflow.execute_activity(
                create_docker_volume_for_registry,
                registry,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            ),
            workflow.execute_activity(
                create_docker_config_for_registry,
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
            config=config,
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
