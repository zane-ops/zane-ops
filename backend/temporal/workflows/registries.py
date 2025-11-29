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
        upsert_registry_url_in_proxy,
        delete_previous_docker_configs_for_registry,
        update_build_registry_swarm_service,
        wait_for_registry_service_to_be_updated,
        acquire_registry_deploy_semaphore,
        release_registry_deploy_semaphore,
        create_registry_health_check_schedule,
        delete_registry_health_check_schedule,
    )

from ..shared import (
    RegistrySnaphot,
    SwarmRegistryServiceDetails,
    DeleteSwarmRegistryServiceDetails,
    UpdateRegistryPayload,
    DeleteSwarmRegistryDomainDetails,
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
                DeleteSwarmRegistryDomainDetails(
                    service_alias=payload.service_alias,
                    domain=payload.domain,
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            ),
            workflow.execute_activity(
                cleanup_docker_registry_service_resources,
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            ),
            workflow.execute_activity(
                delete_registry_health_check_schedule,
                payload,
                start_to_close_timeout=timedelta(seconds=30),
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
    async def run(self, payload: RegistrySnaphot):
        await workflow.execute_activity(
            acquire_registry_deploy_semaphore,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=self.retry_policy,
        )
        try:
            volume, config_data = await asyncio.gather(
                workflow.execute_activity(
                    create_docker_volume_for_registry,
                    payload,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=self.retry_policy,
                ),
                workflow.execute_activity(
                    create_docker_configs_for_registry,
                    payload,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=self.retry_policy,
                ),
            )

            await workflow.execute_activity(
                pull_registry_image,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )

            swarm_details = SwarmRegistryServiceDetails(
                registry=payload,
                configs={
                    cast(str, config.id): config for config in config_data.configs
                },
                volume=volume,
                alias=payload.service_alias,
                swarm_id=payload.swarm_service_name,
            )

            await workflow.execute_activity(
                create_build_registry_swarm_service,
                swarm_details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity(
                upsert_registry_url_in_proxy,
                payload,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity(
                create_registry_health_check_schedule,
                payload,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
        finally:
            await workflow.execute_activity(
                release_registry_deploy_semaphore,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )


@workflow.defn(name="update-build-registry")
class UpdateBuildRegistryWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: UpdateRegistryPayload):
        await workflow.execute_activity(
            acquire_registry_deploy_semaphore,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=self.retry_policy,
        )
        try:
            volume, config_data = await asyncio.gather(
                workflow.execute_activity(
                    create_docker_volume_for_registry,
                    payload.current,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=self.retry_policy,
                ),
                workflow.execute_activity(
                    create_docker_configs_for_registry,
                    payload.current,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=self.retry_policy,
                ),
            )

            await workflow.execute_activity(
                pull_registry_image,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )

            swarm_details = SwarmRegistryServiceDetails(
                registry=payload.current,
                configs={
                    cast(str, config.id): config for config in config_data.configs
                },
                volume=volume,
                alias=payload.service_alias,
                swarm_id=payload.swarm_service_name,
            )

            await workflow.execute_activity(
                update_build_registry_swarm_service,
                swarm_details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity(
                upsert_registry_url_in_proxy,
                payload.current,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity(
                create_registry_health_check_schedule,
                payload.current,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity(
                wait_for_registry_service_to_be_updated,
                payload.previous,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity(
                delete_previous_docker_configs_for_registry,
                payload.previous,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
        finally:
            await workflow.execute_activity(
                release_registry_deploy_semaphore,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
