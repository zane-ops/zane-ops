from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import DockerSwarmActivities
    from .shared import ProjectDetails, ArchivedProjectDetails, DeployServicePayload


@workflow.defn(name="create-project-resources-workflow")
class CreateProjectResourcesWorkflow:
    @workflow.run
    async def run(self, payload: ProjectDetails) -> str:
        print(f"Running workflow CreateProjectResourcesWorkflow with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        network_id = await workflow.execute_activity_method(
            DockerSwarmActivities.create_project_network,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.attach_network_to_proxy,
            network_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        return network_id


@workflow.defn(name="remove-project-resources-workflow")
class RemoveProjectResourcesWorkflow:
    @workflow.run
    async def run(self, payload: ArchivedProjectDetails):
        print(f"Running workflow RemoveProjectResourcesWorkflow with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        # services = await workflow.execute_activity_method(
        #     DockerSwarmActivities.get_archived_project_services,
        #     payload,
        #     start_to_close_timeout=timedelta(seconds=5),
        #     retry_policy=retry_policy,
        # )
        #
        # await asyncio.gather(
        #     *[
        #         workflow.execute_activity_method(
        #             DockerSwarmActivities.unexpose_docker_service_from_http,
        #             service,
        #             start_to_close_timeout=timedelta(seconds=10),
        #             retry_policy=retry_policy,
        #         )
        #         for service in services
        #     ]
        # )
        #
        # await asyncio.gather(
        #     *[
        #         workflow.execute_activity_method(
        #             DockerSwarmActivities.cleanup_docker_service_resources,
        #             service,
        #             start_to_close_timeout=timedelta(seconds=30),
        #             retry_policy=retry_policy,
        #         )
        #         for service in services
        #     ]
        # )

        await workflow.execute_activity_method(
            DockerSwarmActivities.detach_network_from_proxy,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.remove_project_network,
            payload,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )


@workflow.defn(name="deploy-service-workflow")
class DeployServiceWorkflow:
    @workflow.run
    async def run(self, payload: DeployServicePayload):
        workflow.logger.info(f"Running workflow DeployServiceWorkflow with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.prepare_deployment,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )
