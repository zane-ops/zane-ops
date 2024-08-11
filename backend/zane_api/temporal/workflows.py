from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from . import DeploymentStatusResult

with workflow.unsafe.imports_passed_through():
    from ..models import DockerDeployment
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


@workflow.defn(name="deploy-docker-service-workflow")
class DeployDockerServiceWorkflow:
    @workflow.run
    async def run(self, payload: DeployServicePayload):
        print(f"Running workflow `DeployDockerServiceWorkflow` with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=1, maximum_interval=timedelta(seconds=30)
        )

        print(f"Running activity `prepare_deployment({payload=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.prepare_deployment,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        # await workflow.execute_activity_method(
        #     DockerSwarmActivities.create_docker_volumes_for_service,
        #     payload,
        #     start_to_close_timeout=timedelta(seconds=30),
        #     retry_policy=retry_policy,
        # )

        print(
            f"Running activity `create_swarm_service_for_docker_deployment({payload=})`"
        )
        await workflow.execute_activity_method(
            DockerSwarmActivities.create_swarm_service_for_docker_deployment,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        print(f"Running activity `check_docker_deployment_status({payload=})`")
        deployment_status, deployment_status_reason = (
            await workflow.execute_activity_method(
                DockerSwarmActivities.check_docker_deployment_status,
                payload,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
        )

        if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY:
            result = DeploymentStatusResult(
                hash=payload.hash,
                status=deployment_status,
                reason=deployment_status_reason,
            )
            print(f"Running activity `save_deployment_success({result=})`")
            await workflow.execute_activity_method(
                DockerSwarmActivities.save_deployment_success,
                result,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )


def get_workflows_and_activities():
    activities = DockerSwarmActivities()
    return dict(
        workflows=[
            CreateProjectResourcesWorkflow,
            RemoveProjectResourcesWorkflow,
            DeployDockerServiceWorkflow,
        ],
        activities=[
            activities.attach_network_to_proxy,
            activities.create_project_network,
            activities.unexpose_docker_service_from_http,
            activities.detach_network_from_proxy,
            activities.remove_project_network,
            activities.cleanup_docker_service_resources,
            activities.get_archived_project_services,
            activities.prepare_deployment,
            activities.scale_down_service_deployment,
            activities.create_docker_volumes_for_service,
            activities.create_swarm_service_for_docker_deployment,
            activities.check_docker_deployment_status,
            activities.expose_docker_service_deployment_to_http,
            activities.save_deployment_success,
        ],
    )
