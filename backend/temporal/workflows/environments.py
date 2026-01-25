import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ..activities import (
        DockerSwarmActivities,
        GitActivities,
        delete_env_resources,
        ComposeStackActivities,
    )
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
        services = await workflow.execute_activity_method(
            DockerSwarmActivities.get_archived_env_services,
            environment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.unexpose_docker_service_from_http,
                    service,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=self.retry_policy,
                )
                for service in services
            ],
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.unexpose_stack_services_from_http,
                    stack,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=self.retry_policy,
                )
                for stack in environment.compose_stacks
            ],
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.delete_stack_healthcheck_schedule,
                    stack,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=self.retry_policy,
                )
                for stack in environment.compose_stacks
            ]
        )

        all_stack_services = await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.get_services_in_stack,
                    stack,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=self.retry_policy,
                )
                for stack in environment.compose_stacks
            ]
        )

        # flatten the list of services
        all_stack_services = [
            stack_service
            for service_list in all_stack_services
            for stack_service in service_list
        ]

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.cleanup_docker_service_resources,
                    service,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=self.retry_policy,
                )
                for service in services
            ],
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.remove_stack_with_cli,
                    stack,
                    start_to_close_timeout=timedelta(minutes=2, seconds=30),
                    retry_policy=self.retry_policy,
                )
                for stack in environment.compose_stacks
            ],
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.wait_for_stack_service_containers_to_be_deleted,
                    service,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                )
                for service in all_stack_services
            ]
        )

        await workflow.execute_activity_method(
            GitActivities.delete_buildkit_builder_for_env,
            environment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.delete_stack_configs,
                    stack,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
                for stack in environment.compose_stacks
            ],
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.delete_stack_volumes,
                    stack,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
                for stack in environment.compose_stacks
            ],
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
