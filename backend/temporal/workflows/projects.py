import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        DockerSwarmActivities,
        GitActivities,
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

        print(f"Running activity `get_archived_project_services({payload=})`")
        services = await workflow.execute_activity_method(
            DockerSwarmActivities.get_archived_project_services,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        print(f"Running activities `unexpose_docker_service_from_http({services=})`")
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

        print(f"Running activities `cleanup_docker_service_resources({services=})`")
        await asyncio.gather(
            *[
                workflow.execute_activity_method(
                    DockerSwarmActivities.cleanup_docker_service_resources,
                    service,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )
                for service in services
            ]
        )

        print(
            f"Running activities `delete_buildkit_builder_for_env({payload.environments=})`"
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
        print(f"Running activity `remove_project_networks({payload=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.remove_project_networks,
            payload,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )
