import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        DockerSwarmActivities,
        GitActivities,
        ComposeStackActivities,
    )
    from ..shared import (
        ProjectDetails,
        ArchivedProjectDetails,
    )


@workflow.defn(name="create-project-resources-workflow")
class CreateProjectResourcesWorkflow:
    @workflow.run
    async def run(self, payload: ProjectDetails) -> str:
        print(f"Running workflow `CreateProjectResourcesWorkflow` with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        print(f"Running activity `create_project_network({payload=})`")
        network_id = await workflow.execute_activity_method(
            DockerSwarmActivities.create_project_network,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        return network_id


@workflow.defn(name="remove-project-resources-workflow")
class RemoveProjectResourcesWorkflow:
    @workflow.run
    async def run(self, payload: ArchivedProjectDetails):
        print(f"\nRunning workflow `RemoveProjectResourcesWorkflow` with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        services = await workflow.execute_activity_method(
            DockerSwarmActivities.get_archived_project_services,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.unexpose_stack_services_from_http,
                    stack,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=retry_policy,
                )
                for stack in payload.compose_stacks
            ]
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.unexpose_docker_service_from_http,
                    service,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=retry_policy,
                )
                for service in services
            ]
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.delete_stack_healthcheck_schedule,
                    stack,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=retry_policy,
                )
                for stack in payload.compose_stacks
            ]
        )

        all_stack_services = await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.get_services_in_stack,
                    stack,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=retry_policy,
                )
                for stack in payload.compose_stacks
            ]
        )

        # flatten the list of services
        all_stack_services = [
            stack_service
            for service_list in all_stack_services
            for stack_service in service_list
        ]

        coroutines = [
            workflow.execute_activity_method(
                DockerSwarmActivities.cleanup_docker_service_resources,
                service,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )
            for service in services
        ]

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.cleanup_docker_service_resources,
                    service,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )
                for service in services
            ],
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.remove_stack_with_cli,
                    stack,
                    start_to_close_timeout=timedelta(minutes=2, seconds=30),
                    retry_policy=retry_policy,
                )
                for stack in payload.compose_stacks
            ],
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    GitActivities.delete_buildkit_builder_for_env,
                    env,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                for env in payload.environments
            ]
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.wait_for_stack_service_containers_to_be_deleted,
                    service,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=retry_policy,
                )
                for service in all_stack_services
            ]
        )

        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.delete_stack_configs,
                    stack,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                for stack in payload.compose_stacks
            ],
            *[
                workflow.execute_activity_method(
                    ComposeStackActivities.delete_stack_volumes,
                    stack,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                for stack in payload.compose_stacks
            ],
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.remove_project_networks,
            payload,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )
