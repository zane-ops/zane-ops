import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ..activities import DockerSwarmActivities, GitActivities, delete_env_resources
    from ..shared import (
        EnvironmentDetails,
    )


@workflow.defn(name="create-env-network")
class CreateEnvNetworkWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, environment: EnvironmentDetails):
        print(f"Running workflow CreateEnvNetworkWorkflow(payload={environment})")
        return await workflow.execute_activity_method(
            DockerSwarmActivities.create_environment_network,
            arg=environment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )


@workflow.defn(name="archive-env")
class ArchiveEnvWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, environment: EnvironmentDetails):
        print(f"Running workflow ArchiveEnvWorkflow(payload={environment})")
        services = await workflow.execute_activity_method(
            DockerSwarmActivities.get_archived_env_services,
            environment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        print(f"Running activities `unexpose_docker_service_from_http({services=})`")
        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.unexpose_docker_service_from_http,
                    service,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=self.retry_policy,
                )
                for service in services
            ]
        )

        print(f"Running activities `cleanup_docker_service_resources({services=})`")
        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.cleanup_docker_service_resources,
                    service,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=self.retry_policy,
                )
                for service in services
            ]
        )

        await workflow.execute_activity_method(
            GitActivities.delete_buildkit_builder_for_env,
            environment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        return await workflow.execute_activity_method(
            DockerSwarmActivities.delete_environment_network,
            arg=environment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )


@workflow.defn(name="delayed-archive-env")
class DelayedArchiveEnvWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, environment: EnvironmentDetails):
        print(f"Running workflow DelayedArchiveEnvWorkflow(payload={environment})")
        env_found = await workflow.execute_activity(
            delete_env_resources,
            environment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        if env_found:
            return await workflow.execute_child_workflow(
                ArchiveEnvWorkflow.run,
                arg=environment,
                id=environment.archive_workflow_id,
            )
