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
    DeployServiceWorkflowResult,
    DeploymentCreateVolumesResult,
    CancelDeploymentSignalInput,
    ToggleServiceDetails,
    UpdateDetails,
    GitBuildDetails,
    GitCommitDetails,
    GitDeploymentDetailsWithCommitMessage,
)
from ..dtos import ConfigDto, VolumeDto


with workflow.unsafe.imports_passed_through():
    from ..models import Deployment
    from .activities import (
        DockerSwarmActivities,
        SystemCleanupActivities,
        GitActivities,
    )
    from .shared import (
        ProjectDetails,
        ArchivedProjectDetails,
        DeploymentDetails,
        EnvironmentDetails,
    )
    from django.conf import settings
    from .schedules import (
        MonitorDockerDeploymentWorkflow,
        MonitorDockerDeploymentActivities,
        CleanupActivities,
        CleanupAppLogsWorkflow,
        DockerDeploymentStatsActivities,
        GetDockerDeploymentStatsWorkflow,
    )
    from .activities import (
        acquire_deploy_semaphore,
        release_deploy_semaphore,
        lock_deploy_semaphore,
        reset_deploy_semaphore,
    )
    from ..utils import jprint
    from .activities.service_auto_update import (
        update_docker_service,
        update_image_version_in_env_file,
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
        self.cancellation_requested = None
        self.created_volumes: List[VolumeDto] = []
        self.created_configs: List[ConfigDto] = []
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.signal
    def cancel_deployment(self, input: CancelDeploymentSignalInput):
        self.cancellation_requested = input.deployment_hash
        print(f"Sending signal {input=} {self.cancellation_requested=}")

    @workflow.run
    async def run(self, deployment: DeploymentDetails) -> DeployServiceWorkflowResult:
        await workflow.execute_activity(
            acquire_deploy_semaphore,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=self.retry_policy,
        )

        print("Running DeployDockerServiceWorkflow with payload: ")
        jprint(deployment)  # type: ignore
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
                        lambda: self.cancellation_requested == deployment.hash,
                        timeout=timedelta(seconds=5),
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
                (len(service.non_read_only_volumes) > 0 or len(service.ports) > 0)
                and previous_production_deployment is not None
                and previous_production_deployment.status
                != Deployment.DeploymentStatus.FAILED
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
                deployment_status = Deployment.DeploymentStatus.FAILED
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

                if len(deployment.service.urls) > 0:
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

            if deployment_status == Deployment.DeploymentStatus.HEALTHY:
                if len(deployment.service.urls) > 0:
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

            if healthcheck_result.status == Deployment.DeploymentStatus.HEALTHY:
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

                await workflow.execute_activity_method(
                    DockerSwarmActivities.create_deployment_stats_schedule,
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
                    != Deployment.DeploymentStatus.FAILED
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
            await workflow.execute_activity_method(
                DockerSwarmActivities.cleanup_previous_unclean_deployments,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            next_queued_deployment = await self.queue_next_deployment(deployment)
            return DeployServiceWorkflowResult(
                deployment_status=final_deployment_status,
                deployment_status_reason=reason,
                healthcheck_result=healthcheck_result,
                next_queued_deployment=next_queued_deployment,
            )
        except ActivityError as e:
            healthcheck_result = DeploymentHealthcheckResult(
                deployment_hash=deployment.hash,
                status=Deployment.DeploymentStatus.FAILED,
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
            return DeployServiceWorkflowResult(
                deployment_status=final_deployment_status[0],
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
        deployment: DeploymentDetails,
        last_completed_step: DockerDeploymentStep,
    ) -> DeployServiceWorkflowResult:
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
        return DeployServiceWorkflowResult(
            deployment_status=Deployment.DeploymentStatus.CANCELLED,
            next_queued_deployment=next_queued_deployment,
            deployment_status_reason="Deployment cancelled.",
        )

    async def queue_next_deployment(
        self, deployment: DeploymentDetails
    ) -> Optional[DeploymentDetails]:
        next_queued_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_queued_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )
        if next_queued_deployment is not None:
            workflow.continue_as_new(next_queued_deployment)
        return next_queued_deployment

    async def cleanup_previous_production_deployment(
        self,
        previous_deployment: SimpleDeploymentDetails,
        current_deployment: DeploymentDetails,
    ):
        await workflow.execute_activity_method(
            DockerSwarmActivities.delete_previous_production_deployment_schedules,
            previous_deployment,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=self.retry_policy,
        )

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


class GitDeploymentStep(Enum):
    INITIALIZED = auto()
    IMAGE_BUILT = auto()
    VOLUMES_CREATED = auto()
    CONFIGS_CREATED = auto()
    PREVIOUS_DEPLOYMENT_SCALED_DOWN = auto()
    SWARM_SERVICE_CREATED = auto()
    DEPLOYMENT_EXPOSED_TO_HTTP = auto()
    SERVICE_EXPOSED_TO_HTTP = auto()
    FINISHED = auto()

    def __lt__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, GitDeploymentStep):
            return self.value >= other.value
        return NotImplemented


@workflow.defn(name="deploy-git-service-workflow")
class DeployGitServiceWorkflow:
    def __init__(self):
        self.cancellation_requested: Optional[str] = None
        self.tmp_dir: Optional[str] = None
        self.image_built: Optional[str] = None
        self.created_volumes: List[VolumeDto] = []
        self.created_configs: List[ConfigDto] = []
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.signal
    def cancel_deployment(self, input: CancelDeploymentSignalInput):
        self.cancellation_requested = input.deployment_hash
        print(f"Sending signal {input=} {self.cancellation_requested=}")

    @workflow.run
    async def run(self, deployment: DeploymentDetails) -> DeployServiceWorkflowResult:
        await workflow.execute_activity(
            acquire_deploy_semaphore,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=self.retry_policy,
        )

        print("Running DeployGitServiceWorkflow with payload: ")
        jprint(deployment)  # type: ignore
        pause_at_step = (
            GitDeploymentStep(deployment.pause_at_step)
            if deployment.pause_at_step > 0
            else None
        )

        async def check_for_cancellation(
            last_completed_step: GitDeploymentStep,
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
                        lambda: self.cancellation_requested == deployment.hash,
                        timeout=timedelta(seconds=5),
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

            if await check_for_cancellation(GitDeploymentStep.INITIALIZED):
                return await self.handle_cancellation(
                    deployment,
                    GitDeploymentStep.INITIALIZED,
                )

            # build the image
            self.tmp_dir = await workflow.execute_activity_method(
                GitActivities.create_temporary_directory_for_build,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            commit = await workflow.execute_activity_method(
                GitActivities.clone_repository_and_checkout_to_commit,
                GitBuildDetails(
                    deployment=deployment,
                    location=self.tmp_dir,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            if commit is None:
                deployment_status = Deployment.DeploymentStatus.FAILED
                deployment_status_reason = "Failed to clone and checkout repository"
            else:
                await workflow.execute_activity_method(
                    GitActivities.update_deployment_commit_message_and_author,
                    GitDeploymentDetailsWithCommitMessage(
                        commit=commit,
                        deployment=deployment,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
                self.image_built = await workflow.execute_activity_method(
                    GitActivities.build_service_with_dockerfile,
                    GitBuildDetails(
                        deployment=deployment,
                        location=self.tmp_dir,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

                if self.image_built is None:
                    deployment_status = Deployment.DeploymentStatus.FAILED
                    deployment_status_reason = "Failed to checkout repository"
                else:
                    if await check_for_cancellation(GitDeploymentStep.IMAGE_BUILT):
                        return await self.handle_cancellation(
                            deployment,
                            GitDeploymentStep.IMAGE_BUILT,
                        )

                    service = deployment.service
                    if len(service.docker_volumes) > 0:
                        self.created_volumes = await workflow.execute_activity_method(
                            DockerSwarmActivities.create_docker_volumes_for_service,
                            deployment,
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=self.retry_policy,
                        )

                    if await check_for_cancellation(GitDeploymentStep.VOLUMES_CREATED):
                        return await self.handle_cancellation(
                            deployment, GitDeploymentStep.VOLUMES_CREATED
                        )

                    if len(service.configs) > 0:
                        self.created_configs = await workflow.execute_activity_method(
                            DockerSwarmActivities.create_docker_configs_for_service,
                            deployment,
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=self.retry_policy,
                        )

                    if await check_for_cancellation(GitDeploymentStep.CONFIGS_CREATED):
                        return await self.handle_cancellation(
                            deployment, GitDeploymentStep.CONFIGS_CREATED
                        )

                    if (
                        (
                            len(service.non_read_only_volumes) > 0
                            or len(service.ports) > 0
                        )
                        and previous_production_deployment is not None
                        and previous_production_deployment.status
                        != Deployment.DeploymentStatus.FAILED
                    ):
                        await workflow.execute_activity_method(
                            DockerSwarmActivities.scale_down_service_deployment,
                            previous_production_deployment,
                            start_to_close_timeout=timedelta(seconds=60),
                            retry_policy=self.retry_policy,
                        )

                    if await check_for_cancellation(
                        GitDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN
                    ):
                        return await self.handle_cancellation(
                            deployment,
                            GitDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN,
                        )

                    await workflow.execute_activity_method(
                        DockerSwarmActivities.create_swarm_service_for_docker_deployment,
                        deployment,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )

                    if await check_for_cancellation(
                        GitDeploymentStep.SWARM_SERVICE_CREATED
                    ):
                        return await self.handle_cancellation(
                            deployment, GitDeploymentStep.SWARM_SERVICE_CREATED
                        )

                    if len(deployment.service.urls) > 0:
                        await workflow.execute_activity_method(
                            DockerSwarmActivities.expose_docker_deployment_to_http,
                            deployment,
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=self.retry_policy,
                        )

                    if await check_for_cancellation(
                        GitDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP
                    ):
                        return await self.handle_cancellation(
                            deployment, GitDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP
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

            if deployment_status == Deployment.DeploymentStatus.HEALTHY:
                if len(deployment.service.urls) > 0:
                    await workflow.execute_activity_method(
                        DockerSwarmActivities.expose_docker_service_to_http,
                        deployment,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )

                if await check_for_cancellation(
                    GitDeploymentStep.SERVICE_EXPOSED_TO_HTTP
                ):
                    return await self.handle_cancellation(
                        deployment, GitDeploymentStep.SERVICE_EXPOSED_TO_HTTP
                    )

            healthcheck_result = DeploymentHealthcheckResult(
                deployment_hash=deployment.hash,
                status=deployment_status,
                reason=deployment_status_reason,
                service_id=deployment.service.id,
            )

            if healthcheck_result.status == Deployment.DeploymentStatus.HEALTHY:
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

                await workflow.execute_activity_method(
                    DockerSwarmActivities.create_deployment_stats_schedule,
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
                    != Deployment.DeploymentStatus.FAILED
                ):
                    await workflow.execute_activity_method(
                        DockerSwarmActivities.scale_back_service_deployment,
                        previous_production_deployment,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )
                if self.image_built is not None:
                    await workflow.execute_activity_method(
                        GitActivities.cleanup_built_image,
                        self.image_built,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )

            final_deployment_status, reason = await workflow.execute_activity_method(
                DockerSwarmActivities.finish_and_save_deployment,
                healthcheck_result,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.cleanup_previous_unclean_deployments,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            next_queued_deployment = await self.queue_next_deployment(deployment)
            return DeployServiceWorkflowResult(
                deployment_status=final_deployment_status,
                deployment_status_reason=reason,
                healthcheck_result=healthcheck_result,
                next_queued_deployment=next_queued_deployment,
            )
        except ActivityError as e:
            healthcheck_result = DeploymentHealthcheckResult(
                deployment_hash=deployment.hash,
                status=Deployment.DeploymentStatus.FAILED,
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
            return DeployServiceWorkflowResult(
                deployment_status=final_deployment_status[0],
                healthcheck_result=healthcheck_result,
                next_queued_deployment=next_queued_deployment,
                deployment_status_reason=healthcheck_result.reason,
            )
        finally:
            if self.tmp_dir is not None:
                await workflow.execute_activity_method(
                    GitActivities.cleanup_temporary_directory_for_build,
                    GitBuildDetails(
                        deployment=deployment,
                        location=self.tmp_dir,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
            await workflow.execute_activity(
                release_deploy_semaphore,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )

    async def handle_cancellation(
        self,
        deployment: DeploymentDetails,
        last_completed_step: GitDeploymentStep,
    ) -> DeployServiceWorkflowResult:
        if last_completed_step >= GitDeploymentStep.FINISHED:
            raise ApplicationError(
                "Cannot cancel a deployment that already finished", non_retryable=True
            )

        await workflow.execute_activity_method(
            DockerSwarmActivities.toggle_cancelling_status,
            deployment,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=self.retry_policy,
        )

        if last_completed_step >= GitDeploymentStep.SERVICE_EXPOSED_TO_HTTP:
            await workflow.execute_activity_method(
                DockerSwarmActivities.remove_changed_urls_in_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )

        if last_completed_step >= GitDeploymentStep.DEPLOYMENT_EXPOSED_TO_HTTP:
            await workflow.execute_activity_method(
                DockerSwarmActivities.unexpose_docker_deployment_from_http,
                deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=self.retry_policy,
            )

        if last_completed_step >= GitDeploymentStep.SWARM_SERVICE_CREATED:
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
        if last_completed_step >= GitDeploymentStep.PREVIOUS_DEPLOYMENT_SCALED_DOWN:
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
            last_completed_step >= GitDeploymentStep.CONFIGS_CREATED
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
            last_completed_step >= GitDeploymentStep.VOLUMES_CREATED
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

        if (
            last_completed_step >= GitDeploymentStep.IMAGE_BUILT
            and self.image_built is not None
        ):
            await workflow.execute_activity_method(
                GitActivities.cleanup_built_image,
                self.image_built,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

        await workflow.execute_activity_method(
            DockerSwarmActivities.save_cancelled_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )
        next_queued_deployment = await self.queue_next_deployment(deployment)
        return DeployServiceWorkflowResult(
            deployment_status=Deployment.DeploymentStatus.CANCELLED,
            next_queued_deployment=next_queued_deployment,
            deployment_status_reason="Deployment cancelled.",
        )

    async def queue_next_deployment(
        self, deployment: DeploymentDetails
    ) -> Optional[DeploymentDetails]:
        next_queued_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_queued_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )
        if next_queued_deployment is not None:
            workflow.continue_as_new(next_queued_deployment)
        return next_queued_deployment

    async def cleanup_previous_production_deployment(
        self,
        previous_deployment: SimpleDeploymentDetails,
        current_deployment: DeploymentDetails,
    ):
        await workflow.execute_activity_method(
            DockerSwarmActivities.delete_previous_production_deployment_schedules,
            previous_deployment,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=self.retry_policy,
        )

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
    async def run(self, details: ToggleServiceDetails):
        print("\nRunning workflow `ToggleDockerServiceWorkflow` with payload=")
        jprint(details)
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        if details.desired_state == "start":
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_back_service_deployment,
                details.deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )
        else:
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_service_deployment,
                details.deployment,
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

        return await workflow.execute_activity_method(
            DockerSwarmActivities.delete_environment_network,
            arg=environment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )


@workflow.defn(name="auto-update-docker-service-workflow")
class AutoUpdateDockerServiceWorkflow:
    @workflow.run
    async def run(self, desired_version: str):
        print(
            f"\nRunning workflow `AutoUpdateDockerServiceWorkflow` with {desired_version=}"
        )

        retry_policy = RetryPolicy(
            maximum_attempts=5,
            maximum_interval=timedelta(seconds=30),
        )

        services_to_update = [
            ("zane_proxy", "ghcr.io/zane-ops/proxy"),
            ("zane_app", "ghcr.io/zane-ops/app"),
            ("zane_temporal-schedule-worker", "ghcr.io/zane-ops/app"),
            ("zane_temporal-main-worker", "ghcr.io/zane-ops/app"),
        ]

        for service, image in services_to_update:
            print(
                f"Running activity `update_docker_service({service=}, {desired_version=})`"
            )
            await workflow.execute_activity(
                update_docker_service,
                UpdateDetails(
                    service_name=service,
                    desired_version=desired_version,
                    service_image=image,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            print(f"Service `{service}` updated successfully.")

        await workflow.execute_activity(
            update_image_version_in_env_file,
            desired_version,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )


def get_workflows_and_activities():
    swarm_activities = DockerSwarmActivities()
    monitor_activities = MonitorDockerDeploymentActivities()
    cleanup_activites = CleanupActivities()
    system_cleanup_activities = SystemCleanupActivities()
    metrics_activities = DockerDeploymentStatsActivities()
    git_activities = GitActivities()

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
            GetDockerDeploymentStatsWorkflow,
            AutoUpdateDockerServiceWorkflow,
            CreateEnvNetworkWorkflow,
            ArchiveEnvWorkflow,
            DeployGitServiceWorkflow,
        ],
        activities=[
            git_activities.create_temporary_directory_for_build,
            git_activities.cleanup_temporary_directory_for_build,
            git_activities.clone_repository_and_checkout_to_commit,
            git_activities.update_deployment_commit_message_and_author,
            git_activities.build_service_with_dockerfile,
            git_activities.cleanup_built_image,
            metrics_activities.get_deployment_stats,
            metrics_activities.save_deployment_stats,
            swarm_activities.toggle_cancelling_status,
            swarm_activities.create_environment_network,
            swarm_activities.get_archived_env_services,
            swarm_activities.delete_environment_network,
            swarm_activities.save_cancelled_deployment,
            swarm_activities.create_deployment_stats_schedule,
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
            swarm_activities.cleanup_previous_unclean_deployments,
            swarm_activities.delete_previous_production_deployment_schedules,
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
            cleanup_activites.cleanup_service_metrics,
            system_cleanup_activities.cleanup_images,
            system_cleanup_activities.cleanup_containers,
            system_cleanup_activities.cleanup_volumes,
            system_cleanup_activities.cleanup_networks,
            acquire_deploy_semaphore,
            lock_deploy_semaphore,
            release_deploy_semaphore,
            reset_deploy_semaphore,
            update_docker_service,
            update_image_version_in_env_file,
        ],
    )
