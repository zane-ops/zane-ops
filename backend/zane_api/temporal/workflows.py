import asyncio
from datetime import timedelta
from enum import Enum, auto
from typing import Optional, List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError, ActivityError

from .shared import (
    DeploymentCreateConfigsResult,
    DeploymentHealthcheckResult,
    SimpleDeploymentDetails,
    ArchivedServiceDetails,
    DeployDockerServiceWorkflowResult,
    DeploymentCreateVolumesResult,
    CancelDeploymentSignalInput,
)
from ..dtos import ConfigDto, VolumeDto

with workflow.unsafe.imports_passed_through():
    from ..models import DockerDeployment
    from .activities import DockerSwarmActivities, SystemCleanupActivities
    from .shared import (
        ProjectDetails,
        ArchivedProjectDetails,
        DockerDeploymentDetails,
    )
    from django.conf import settings
    from .schedules import (
        MonitorDockerDeploymentWorkflow,
        MonitorDockerDeploymentActivities,
        CleanupActivities,
        CleanupAppLogsWorkflow,
    )
    from .activities import (
        acquire_deploy_semaphore,
        release_deploy_semaphore,
        lock_deploy_semaphore,
        reset_deploy_semaphore,
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
    CONFIGS_CREATED = auto()
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
        self.created_configs: List[ConfigDto] = []
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
        await workflow.execute_activity(
            acquire_deploy_semaphore,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=self.retry_policy,
        )

        self.deployment_hash = deployment.hash

        print(
            f"\nRunning workflow `DeployDockerServiceWorkflow` with payload={deployment}"
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
                start_time = workflow.time()
                print(f"{workflow.time()=}, {start_time=}")
                try:
                    await workflow.wait_condition(
                        lambda: self.cancellation_requested,
                        timeout=timedelta(seconds=60),
                    )
                except TimeoutError as error:
                    print(f"TimeoutError {error=}")
                print(
                    f"result check_for_cancellation({pause_at_step=}, {last_completed_step=}) = {self.cancellation_requested}"
                )
            return self.cancellation_requested

        try:
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

            if len(service.configs) > 0:
                self.created_configs = await workflow.execute_activity_method(
                    DockerSwarmActivities.create_docker_configs_for_service,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

            if await check_for_cancellation(DockerDeploymentStep.CONFIGS_CREATED):
                return await self.handle_cancellation(
                    deployment, DockerDeploymentStep.CONFIGS_CREATED
                )

            if (
                (
                    len(service.non_read_only_volumes) > 0
                    or len(service.non_http_ports) > 0
                )
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

            image_pulled_successfully = await workflow.execute_activity_method(
                DockerSwarmActivities.pull_image_for_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )
            if not image_pulled_successfully:
                deployment_status = DockerDeployment.DeploymentStatus.FAILED
                deployment_status_reason = "Failed to pull image"
            else:
                await workflow.execute_activity_method(
                    DockerSwarmActivities.create_swarm_service_for_docker_deployment,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

                if await check_for_cancellation(
                    DockerDeploymentStep.SWARM_SERVICE_CREATED
                ):
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
                        start_to_close_timeout=timedelta(
                            seconds=healthcheck_timeout + 5
                        ),
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

                if await check_for_cancellation(
                    DockerDeploymentStep.SERVICE_EXPOSED_TO_HTTP
                ):
                    return await self.handle_cancellation(
                        deployment, DockerDeploymentStep.SERVICE_EXPOSED_TO_HTTP
                    )

            healthcheck_result = DeploymentHealthcheckResult(
                deployment_hash=deployment.hash,
                status=deployment_status,
                reason=deployment_status_reason,
                service_id=deployment.service.id,
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
            final_deployment_status, reason = await workflow.execute_activity_method(
                DockerSwarmActivities.finish_and_save_deployment,
                healthcheck_result,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
            next_queued_deployment = await self.queue_next_deployment(deployment)
            return DeployDockerServiceWorkflowResult(
                deployment_status=final_deployment_status,
                deployment_status_reason=reason,
                healthcheck_result=healthcheck_result,
                next_queued_deployment=next_queued_deployment,
            )
        except ActivityError as e:
            healthcheck_result = DeploymentHealthcheckResult(
                deployment_hash=deployment.hash,
                status=DockerDeployment.DeploymentStatus.FAILED,
                reason=str(e.cause),
                service_id=deployment.service.id,
            )
            final_deployment_status = await workflow.execute_activity_method(
                DockerSwarmActivities.finish_and_save_deployment,
                healthcheck_result,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
            next_queued_deployment = await self.queue_next_deployment(deployment)
            return DeployDockerServiceWorkflowResult(
                deployment_status=final_deployment_status,
                healthcheck_result=healthcheck_result,
                next_queued_deployment=next_queued_deployment,
                deployment_status_reason=healthcheck_result.reason,
            )
        finally:
            await workflow.execute_activity(
                release_deploy_semaphore,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
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

        await workflow.execute_activity_method(
            DockerSwarmActivities.toggle_cancelling_status,
            deployment,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=self.retry_policy,
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
            last_completed_step >= DockerDeploymentStep.CONFIGS_CREATED
            and len(self.created_configs) > 0
        ):
            await workflow.execute_activity_method(
                DockerSwarmActivities.delete_created_configs,
                DeploymentCreateConfigsResult(
                    deployment_hash=deployment.hash,
                    service_id=deployment.service.id,
                    created_configs=self.created_configs,
                ),
                start_to_close_timeout=timedelta(seconds=5),
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
            deployment_status_reason="Deployment cancelled.",
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
            DockerSwarmActivities.remove_old_docker_configs,
            current_deployment,
            start_to_close_timeout=timedelta(seconds=30),
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


@workflow.defn(name="system-cleanup")
class SystemCleanupWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self):
        await workflow.execute_activity(
            lock_deploy_semaphore,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=self.retry_policy,
        )

        try:
            await workflow.execute_activity_method(
                SystemCleanupActivities.cleanup_images,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                SystemCleanupActivities.cleanup_containers,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                SystemCleanupActivities.cleanup_volumes,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                SystemCleanupActivities.cleanup_networks,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

        finally:
            # release all deployment locks
            await workflow.execute_activity(
                reset_deploy_semaphore,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
            pass


def get_workflows_and_activities():
    swarm_activities = DockerSwarmActivities()
    monitor_activities = MonitorDockerDeploymentActivities()
    cleanup_activites = CleanupActivities()
    system_cleanup_activities = SystemCleanupActivities()

    return dict(
        workflows=[
            ArchiveDockerServiceWorkflow,
            CreateProjectResourcesWorkflow,
            RemoveProjectResourcesWorkflow,
            DeployDockerServiceWorkflow,
            MonitorDockerDeploymentWorkflow,
            ToggleDockerServiceWorkflow,
            CleanupAppLogsWorkflow,
            SystemCleanupWorkflow,
        ],
        activities=[
            swarm_activities.toggle_cancelling_status,
            swarm_activities.save_cancelled_deployment,
            monitor_activities.monitor_close_faulty_db_connections,
            swarm_activities.unexpose_docker_deployment_from_http,
            swarm_activities.remove_changed_urls_in_deployment,
            swarm_activities.create_project_network,
            swarm_activities.unexpose_docker_service_from_http,
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
            swarm_activities.remove_old_docker_configs,
            swarm_activities.remove_old_urls,
            swarm_activities.create_docker_configs_for_service,
            swarm_activities.get_previous_queued_deployment,
            swarm_activities.get_previous_production_deployment,
            swarm_activities.scale_back_service_deployment,
            swarm_activities.create_deployment_healthcheck_schedule,
            swarm_activities.delete_created_configs,
            monitor_activities.save_deployment_status,
            monitor_activities.run_deployment_monitor_healthcheck,
            cleanup_activites.cleanup_simple_logs,
            system_cleanup_activities.cleanup_images,
            system_cleanup_activities.cleanup_containers,
            system_cleanup_activities.cleanup_volumes,
            system_cleanup_activities.cleanup_networks,
            acquire_deploy_semaphore,
            lock_deploy_semaphore,
            release_deploy_semaphore,
            reset_deploy_semaphore,
        ],
    )
