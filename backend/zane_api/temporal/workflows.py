import asyncio
from datetime import timedelta
from enum import Enum, auto
from typing import Optional, List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from .shared import (
    DeploymentHealthcheckResult,
    SimpleDeploymentDetails,
    ArchivedServiceDetails,
    DeployDockerServiceWorkflowResult,
    DeploymentCreateVolumesResult,
    CancelDeploymentSignalInput,
)
from ..dtos import VolumeDto

with workflow.unsafe.imports_passed_through():
    from ..models import DockerDeployment
    from .activities import DockerSwarmActivities
    from .shared import ProjectDetails, ArchivedProjectDetails, DockerDeploymentDetails
    from django.conf import settings
    from .schedules import (
        MonitorDockerDeploymentWorkflow,
        MonitorDockerDeploymentActivities,
    )


@workflow.defn(name="create-project-resources-workflow")
class CreateProjectResourcesWorkflow:
    @workflow.run
    async def run(self, payload: ProjectDetails) -> str:
        print(f"Running workflow `CreateProjectResourcesWorkflow` with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.close_faulty_db_connections,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )

        print(f"Running activity `create_project_network({payload=})`")
        network_id = await workflow.execute_activity_method(
            DockerSwarmActivities.create_project_network,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        print(f"Running activity `attach_network_to_proxy({network_id=})`")
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
        print(f"\nRunning workflow `RemoveProjectResourcesWorkflow` with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.close_faulty_db_connections,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
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

        print(f"Running activity `detach_network_from_proxy({payload=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.detach_network_from_proxy,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        print(f"Running activity `remove_project_network({payload=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.remove_project_network,
            payload,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )


class DockerDeploymentStep(Enum):
    INITIALIZED = auto()
    VOLUMES_CREATED = auto()
    PREVIOUS_DEPLOYMENT_SCALED_DOWN = auto()
    SWARM_SERVICE_CREATED = auto()
    DEPLOYMENT_EXPOSED_TO_HTTP = auto()
    SERVICE_EXPOSED_TO_HTTP = auto()
    FINISHED = auto()

    def __lt__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, DockerDeploymentStep):
            return self.value >= other.value
        return NotImplemented


@workflow.defn(name="deploy-docker-service-workflow")
class DeployDockerServiceWorkflow:
    def __init__(self):
        self.cancellation_requested = False
        self.created_volumes: List[VolumeDto] = []
        self.deployment_hash: str = None
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.signal
    def cancel_deployment(self, input: CancelDeploymentSignalInput):
        if self.deployment_hash == input.deployment_hash:
            self.cancellation_requested = True

    @workflow.run
    async def run(
        self, deployment: DockerDeploymentDetails
    ) -> DeployDockerServiceWorkflowResult:
        self.deployment_hash = deployment.hash

        print(
            f"\nRunning workflow `DeployDockerServiceWorkflow` with payload={deployment}"
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.close_faulty_db_connections,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=self.retry_policy,
        )

        pause_at_step = (
            DockerDeploymentStep(deployment.pause_at_step)
            if deployment.pause_at_step > 0
            else None
        )

        async def check_for_cancellation(
            last_completed_step: DockerDeploymentStep,
        ):
            """
            This function allows us to pause and potentially bypass the workflow's execution
            during testing. It is useful for stopping the workflow at specific points to
            simulate and handle cancellation.

            Because workflows are asynchronous, the workflow might progress to another step
            by the time the user triggers `cancel_deployment`. This function helps ensure
            that the workflow can pause at a predefined step (indicated by `pause_at_step`)
            and wait for a cancellation signal.

            Note: `pause_at_step`  is intended only for testing and should not be used in
            the application logic.
            """
            if pause_at_step is not None:
                if pause_at_step != last_completed_step:
                    return False

                print(
                    f"await check_for_cancellation({pause_at_step=}, {last_completed_step=})"
                )
                timeout = 5
                start_time = workflow.time()
                while (
                    workflow.time() - start_time
                ) < timeout and not self.cancellation_requested:
                    await asyncio.sleep(1)
                print(
                    f"result check_for_cancellation({pause_at_step=}, {last_completed_step=}) = {self.cancellation_requested}"
                )
            return self.cancellation_requested

        await workflow.execute_activity_method(
            DockerSwarmActivities.prepare_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        previous_production_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_production_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        if await check_for_cancellation(DockerDeploymentStep.INITIALIZED):
            return await self.handle_cancellation(
                deployment,
                DockerDeploymentStep.INITIALIZED,
            )

        service = deployment.service
        if len(service.docker_volumes) > 0:
            self.created_volumes = await workflow.execute_activity_method(
                DockerSwarmActivities.create_docker_volumes_for_service,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

        if await check_for_cancellation(DockerDeploymentStep.VOLUMES_CREATED):
            return await self.handle_cancellation(
                deployment, DockerDeploymentStep.VOLUMES_CREATED
            )

        if (
            (len(service.volumes) > 0 or len(service.non_http_ports) > 0)
            and previous_production_deployment is not None
            and previous_production_deployment.status
            != DockerDeployment.DeploymentStatus.FAILED
        ):
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_service_deployment,
                previous_production_deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )

        if await check_for_cancellation(
            DockerDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN
        ):
            return await self.handle_cancellation(
                deployment, DockerDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN
            )

        await workflow.execute_activity_method(
            DockerSwarmActivities.pull_image_for_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.create_swarm_service_for_docker_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        if await check_for_cancellation(DockerDeploymentStep.SWARM_SERVICE_CREATED):
            return await self.handle_cancellation(
                deployment, DockerDeploymentStep.SWARM_SERVICE_CREATED
            )

        if deployment.service.http_port is not None:
            await workflow.execute_activity_method(
                DockerSwarmActivities.expose_docker_deployment_to_http,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

        if await check_for_cancellation(
            DockerDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP
        ):
            return await self.handle_cancellation(
                deployment, DockerDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP
            )

        healthcheck_timeout = (
            deployment.service.healthcheck.timeout_seconds
            if deployment.service.healthcheck is not None
            else settings.DEFAULT_HEALTHCHECK_TIMEOUT
        )
        deployment_status, deployment_status_reason = (
            await workflow.execute_activity_method(
                DockerSwarmActivities.run_deployment_healthcheck,
                deployment,
                retry_policy=self.retry_policy,
                start_to_close_timeout=timedelta(seconds=healthcheck_timeout + 5),
            )
        )

        if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY:
            if deployment.service.http_port is not None:
                await workflow.execute_activity_method(
                    DockerSwarmActivities.expose_docker_service_to_http,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

        if await check_for_cancellation(DockerDeploymentStep.SERVICE_EXPOSED_TO_HTTP):
            return await self.handle_cancellation(
                deployment, DockerDeploymentStep.SERVICE_EXPOSED_TO_HTTP
            )

        healthcheck_result = DeploymentHealthcheckResult(
            deployment_hash=deployment.hash,
            status=deployment_status,
            reason=deployment_status_reason,
            service_id=deployment.service.id,
        )
        final_deployment_status = await workflow.execute_activity_method(
            DockerSwarmActivities.finish_and_save_deployment,
            healthcheck_result,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        if healthcheck_result.status == DockerDeployment.DeploymentStatus.HEALTHY:
            if previous_production_deployment is not None:
                await self.cleanup_previous_production_deployment(
                    previous_deployment=previous_production_deployment,
                    current_deployment=deployment,
                )

            await workflow.execute_activity_method(
                DockerSwarmActivities.create_deployment_healthcheck_schedule,
                deployment,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
        else:
            current_deployment = SimpleDeploymentDetails(
                hash=deployment.hash,
                project_id=deployment.service.project_id,
                service_id=deployment.service.id,
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_and_remove_docker_service_deployment,
                current_deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )
            if (
                previous_production_deployment is not None
                and previous_production_deployment.status
                != DockerDeployment.DeploymentStatus.FAILED
            ):
                await workflow.execute_activity_method(
                    DockerSwarmActivities.scale_back_service_deployment,
                    previous_production_deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

        next_queued_deployment = await self.queue_next_deployment(deployment)
        return DeployDockerServiceWorkflowResult(
            deployment_status=final_deployment_status,
            healthcheck_result=healthcheck_result,
            next_queued_deployment=next_queued_deployment,
        )

    async def handle_cancellation(
        self,
        deployment: DockerDeploymentDetails,
        last_completed_step: DockerDeploymentStep,
    ) -> DeployDockerServiceWorkflowResult:
        if last_completed_step >= DockerDeploymentStep.FINISHED:
            raise ApplicationError(
                "Cannot cancel a deployment that already finished", non_retryable=True
            )

        if last_completed_step >= DockerDeploymentStep.SERVICE_EXPOSED_TO_HTTP:
            await workflow.execute_activity_method(
                DockerSwarmActivities.remove_changed_urls_in_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )

        if last_completed_step >= DockerDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP:
            await workflow.execute_activity_method(
                DockerSwarmActivities.unexpose_docker_deployment_from_http,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )

        if last_completed_step >= DockerDeploymentStep.SWARM_SERVICE_CREATED:
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_and_remove_docker_service_deployment,
                SimpleDeploymentDetails(
                    hash=deployment.hash,
                    service_id=deployment.service.id,
                    project_id=deployment.service.project_id,
                ),
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )
        if last_completed_step >= DockerDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN:
            previous_production_deployment = await workflow.execute_activity_method(
                DockerSwarmActivities.get_previous_production_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
            if previous_production_deployment is not None:
                await workflow.execute_activity_method(
                    DockerSwarmActivities.scale_back_service_deployment,
                    previous_production_deployment,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=self.retry_policy,
                )
        if (
            last_completed_step >= DockerDeploymentStep.VOLUMES_CREATED
            and len(self.created_volumes) > 0
        ):
            await workflow.execute_activity_method(
                DockerSwarmActivities.delete_created_volumes,
                DeploymentCreateVolumesResult(
                    deployment_hash=deployment.hash,
                    service_id=deployment.service.id,
                    created_volumes=self.created_volumes,
                ),
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )

        await workflow.execute_activity_method(
            DockerSwarmActivities.save_cancelled_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )
        next_queued_deployment = await self.queue_next_deployment(deployment)
        return DeployDockerServiceWorkflowResult(
            deployment_status=DockerDeployment.DeploymentStatus.CANCELLED,
            next_queued_deployment=next_queued_deployment,
        )

    async def queue_next_deployment(
        self, deployment: DockerDeploymentDetails
    ) -> Optional[DockerDeploymentDetails]:
        next_queued_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_queued_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )
        if next_queued_deployment is not None:
            await workflow.continue_as_new(next_queued_deployment)
        return next_queued_deployment

    async def cleanup_previous_production_deployment(
        self,
        previous_deployment: SimpleDeploymentDetails,
        current_deployment: DockerDeploymentDetails,
    ):
        await workflow.execute_activity_method(
            DockerSwarmActivities.scale_down_and_remove_docker_service_deployment,
            previous_deployment,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.remove_old_docker_volumes,
            current_deployment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.remove_old_urls,
            current_deployment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.cleanup_previous_production_deployment,
            previous_deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )


@workflow.defn(name="archive-docker-service-workflow")
class ArchiveDockerServiceWorkflow:
    @workflow.run
    async def run(self, service: ArchivedServiceDetails):
        print(f"\nRunning workflow `ArchiveDockerServiceWorkflow` with {service=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.close_faulty_db_connections,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )

        print(f"Running activity `unexpose_docker_service_from_http({service=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.unexpose_docker_service_from_http,
            service,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )

        print(f"Running activity `cleanup_docker_service_resources({service=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.cleanup_docker_service_resources,
            service,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )


@workflow.defn(name="toggle-docker-service-state-workflow")
class ToggleDockerServiceWorkflow:
    @workflow.run
    async def run(self, deployment: SimpleDeploymentDetails):
        print(f"\nRunning workflow `ToggleDockerServiceWorkflow` with {deployment=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        await workflow.execute_activity_method(
            DockerSwarmActivities.close_faulty_db_connections,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy,
        )

        if deployment.status == DockerDeployment.DeploymentStatus.SLEEPING:
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_back_service_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )
        else:
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_service_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )


def get_workflows_and_activities():
    swarm_activities = DockerSwarmActivities()
    monitor_activities = MonitorDockerDeploymentActivities()
    return dict(
        workflows=[
            ArchiveDockerServiceWorkflow,
            CreateProjectResourcesWorkflow,
            RemoveProjectResourcesWorkflow,
            DeployDockerServiceWorkflow,
            MonitorDockerDeploymentWorkflow,
            ToggleDockerServiceWorkflow,
        ],
        activities=[
            swarm_activities.save_cancelled_deployment,
            swarm_activities.close_faulty_db_connections,
            monitor_activities.monitor_close_faulty_db_connections,
            swarm_activities.unexpose_docker_deployment_from_http,
            swarm_activities.remove_changed_urls_in_deployment,
            swarm_activities.attach_network_to_proxy,
            swarm_activities.create_project_network,
            swarm_activities.unexpose_docker_service_from_http,
            swarm_activities.detach_network_from_proxy,
            swarm_activities.remove_project_network,
            swarm_activities.cleanup_docker_service_resources,
            swarm_activities.get_archived_project_services,
            swarm_activities.prepare_deployment,
            swarm_activities.scale_down_service_deployment,
            swarm_activities.pull_image_for_deployment,
            swarm_activities.create_docker_volumes_for_service,
            swarm_activities.delete_created_volumes,
            swarm_activities.create_swarm_service_for_docker_deployment,
            swarm_activities.run_deployment_healthcheck,
            swarm_activities.expose_docker_deployment_to_http,
            swarm_activities.expose_docker_service_to_http,
            swarm_activities.finish_and_save_deployment,
            swarm_activities.cleanup_previous_production_deployment,
            swarm_activities.scale_down_and_remove_docker_service_deployment,
            swarm_activities.remove_old_docker_volumes,
            swarm_activities.remove_old_urls,
            swarm_activities.get_previous_queued_deployment,
            swarm_activities.get_previous_production_deployment,
            swarm_activities.scale_back_service_deployment,
            swarm_activities.create_deployment_healthcheck_schedule,
            monitor_activities.save_deployment_status,
            monitor_activities.run_deployment_monitor_healthcheck,
        ],
    )
