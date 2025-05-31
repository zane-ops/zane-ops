import asyncio
from datetime import timedelta
from typing import Optional, List, cast

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import (
    ApplicationError,
    ActivityError,
    is_cancelled_exception,
)
from temporalio.workflow import ActivityHandle

from ..shared import (
    DeploymentCreateConfigsResult,
    DeploymentHealthcheckResult,
    DockerfileBuilderDetails,
    GitCloneDetails,
    SimpleDeploymentDetails,
    ArchivedDockerServiceDetails,
    ArchivedGitServiceDetails,
    DeployServiceWorkflowResult,
    DeploymentCreateVolumesResult,
    CancelDeploymentSignalInput,
    StaticBuilderDetails,
    NixpacksBuilderDetails,
    ToggleServiceDetails,
    GitBuildDetails,
    GitDeploymentDetailsWithCommitMessage,
    RailpackBuilderDetails,
)
from zane_api.dtos import (
    ConfigDto,
    DockerfileBuilderOptions,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
    VolumeDto,
    EnvVariableDto,
)

with workflow.unsafe.imports_passed_through():
    from zane_api.models import Deployment, Service
    from ..activities import (
        DockerSwarmActivities,
        GitActivities,
        get_all_previous_cancellable_deployments,
        cancel_non_started_deployments,
    )
    from ..shared import (
        DeploymentDetails,
    )
    from django.conf import settings
    from ..activities import (
        acquire_deploy_semaphore,
        release_deploy_semaphore,
    )
    from zane_api.utils import jprint
    from ..helpers import GitDeploymentStep, DockerDeploymentStep


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

        if deployment.cancel_previous and False:
            await workflow.execute_activity(
                cancel_non_started_deployments,
                deployment,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )

            cancellable_deployments = await workflow.execute_activity(
                get_all_previous_cancellable_deployments,
                deployment,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=self.retry_policy,
            )

            for dpl in cancellable_deployments:
                handle = workflow.get_external_workflow_handle_for(
                    DeployDockerServiceWorkflow.run, dpl.workflow_id
                )
                await handle.signal(
                    DeployDockerServiceWorkflow.cancel_deployment,
                    CancelDeploymentSignalInput(deployment_hash=dpl.hash),
                )

        async def check_for_cancellation(
            last_completed_step: DockerDeploymentStep,
        ) -> bool:
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
            return self.cancellation_requested == deployment.hash

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
        print(f"Received signal {input=} {self.cancellation_requested=}")

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
        ) -> bool:
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
            return self.cancellation_requested == deployment.hash

        async def monitor_cancellation(
            activity_handle: ActivityHandle,
            timeout: timedelta = timedelta(seconds=30),
            step_to_pause: GitDeploymentStep | None = None,
        ):
            try:
                if pause_at_step is not None:
                    if pause_at_step != step_to_pause:
                        return
                print(f"await monitor_cancellation({activity_handle.get_name()})")
                await workflow.wait_condition(
                    lambda: self.cancellation_requested == deployment.hash,
                    timeout=timeout,
                )
                print(f"cancelling activity {activity_handle.get_name()}")
            except (asyncio.CancelledError, TimeoutError):
                pass  # do nothing
            else:
                activity_handle.cancel()

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

            self.tmp_dir = await workflow.execute_activity_method(
                GitActivities.create_temporary_directory_for_build,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            clone_repository_activity_handle = workflow.start_activity_method(
                GitActivities.clone_repository_and_checkout_to_commit,
                GitCloneDetails(
                    deployment=deployment,
                    tmp_dir=self.tmp_dir,
                ),
                start_to_close_timeout=timedelta(minutes=2, seconds=30),
                retry_policy=self.retry_policy,
                heartbeat_timeout=timedelta(seconds=3),
            )
            monitor_task = asyncio.create_task(
                monitor_cancellation(
                    clone_repository_activity_handle,
                    step_to_pause=GitDeploymentStep.CLONING_REPOSITORY,
                    timeout=timedelta(minutes=2, seconds=30),
                )
            )

            try:
                commit = await clone_repository_activity_handle
                monitor_task.cancel()
            except ActivityError as e:
                if (
                    is_cancelled_exception(e)
                    and self.cancellation_requested == deployment.hash
                ):
                    return await self.handle_cancellation(
                        deployment,
                        last_completed_step=GitDeploymentStep.CLONING_REPOSITORY,
                    )
                raise  # reraise the same exception

            if await check_for_cancellation(GitDeploymentStep.REPOSITORY_CLONED):
                return await self.handle_cancellation(
                    deployment,
                    GitDeploymentStep.REPOSITORY_CLONED,
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
                build_stage_target = None
                dockerfile_path = None
                build_context_dir = None
                env_variables: List[EnvVariableDto] | None = None
                match deployment.service.builder:
                    case Service.Builder.DOCKERFILE:
                        builder_options = cast(
                            DockerfileBuilderOptions,
                            deployment.service.dockerfile_builder_options,
                        )

                        result = await workflow.execute_activity_method(
                            GitActivities.generate_default_files_for_dockerfile_builder,
                            DockerfileBuilderDetails(
                                deployment=deployment,
                                temp_build_dir=self.tmp_dir,
                                builder_options=builder_options,
                            ),
                            start_to_close_timeout=timedelta(seconds=5),
                            retry_policy=self.retry_policy,
                        )
                        build_stage_target = builder_options.build_stage_target
                        dockerfile_path = result.dockerfile_path
                        build_context_dir = result.build_context_dir
                    case Service.Builder.STATIC_DIR:
                        builder_options = cast(
                            StaticDirectoryBuilderOptions,
                            deployment.service.static_dir_builder_options,
                        )

                        result = await workflow.execute_activity_method(
                            GitActivities.generate_default_files_for_static_builder,
                            StaticBuilderDetails(
                                deployment=deployment,
                                temp_build_dir=self.tmp_dir,
                                builder_options=builder_options,
                            ),
                            start_to_close_timeout=timedelta(seconds=5),
                            retry_policy=self.retry_policy,
                        )
                        dockerfile_path = result.dockerfile_path
                        build_context_dir = result.build_context_dir
                    case Service.Builder.NIXPACKS:
                        builder_options = cast(
                            NixpacksBuilderOptions,
                            deployment.service.nixpacks_builder_options,
                        )

                        result = await workflow.execute_activity_method(
                            GitActivities.generate_default_files_for_nixpacks_builder,
                            NixpacksBuilderDetails(
                                deployment=deployment,
                                temp_build_dir=self.tmp_dir,
                                builder_options=builder_options,
                            ),
                            start_to_close_timeout=timedelta(seconds=5),
                            retry_policy=self.retry_policy,
                        )
                        if result is not None:
                            dockerfile_path = result.dockerfile_path
                            build_context_dir = result.build_context_dir
                            env_variables = result.variables
                    case Service.Builder.RAILPACK:
                        builder_options = cast(
                            NixpacksBuilderOptions,
                            deployment.service.railpack_builder_options,
                        )
                        result = await workflow.execute_activity_method(
                            GitActivities.generate_default_files_for_railpack_builder,
                            RailpackBuilderDetails(
                                deployment=deployment,
                                temp_build_dir=self.tmp_dir,
                                builder_options=builder_options,
                            ),
                            start_to_close_timeout=timedelta(seconds=5),
                            retry_policy=self.retry_policy,
                        )
                        if result is not None:
                            dockerfile_path = result.railpack_plan_path
                            build_context_dir = result.build_context_dir
                    case _:
                        raise Exception(
                            f"Unsupported builder `{deployment.service.builder}`"
                        )

                if build_context_dir is None or dockerfile_path is None:
                    deployment_status = Deployment.DeploymentStatus.FAILED
                    deployment_status_reason = "Deployment failed"
                else:
                    await workflow.execute_activity_method(
                        GitActivities.create_buildkit_builder_for_env,
                        deployment,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )

                    if deployment.service.builder != Service.Builder.RAILPACK:
                        build_image_activity_task = workflow.start_activity_method(
                            GitActivities.build_service_with_dockerfile,
                            GitBuildDetails(
                                deployment=deployment,
                                temp_build_dir=self.tmp_dir,
                                build_context_dir=build_context_dir,
                                dockerfile_path=dockerfile_path,
                                build_stage_target=build_stage_target,
                                image_tag=cast(str, deployment.image_tag),
                                default_env_variables=env_variables,
                            ),
                            start_to_close_timeout=timedelta(minutes=20),
                            heartbeat_timeout=timedelta(seconds=3),
                            retry_policy=RetryPolicy(
                                maximum_attempts=1
                            ),  # We do not want to retry the build multiple times
                        )
                    else:
                        build_image_activity_task = workflow.start_activity_method(
                            GitActivities.build_service_with_railpack_dockerfile,
                            GitBuildDetails(
                                deployment=deployment,
                                temp_build_dir=self.tmp_dir,
                                build_context_dir=build_context_dir,
                                dockerfile_path=dockerfile_path,
                                build_stage_target=build_stage_target,
                                image_tag=cast(str, deployment.image_tag),
                                default_env_variables=env_variables,
                            ),
                            start_to_close_timeout=timedelta(minutes=20),
                            heartbeat_timeout=timedelta(seconds=3),
                            retry_policy=RetryPolicy(
                                maximum_attempts=1
                            ),  # We do not want to retry the build multiple times
                        )

                    monitor_task = asyncio.create_task(
                        monitor_cancellation(
                            build_image_activity_task,
                            step_to_pause=GitDeploymentStep.BUILDING_IMAGE,
                            timeout=timedelta(minutes=20),
                        )
                    )

                    try:
                        self.image_built = await build_image_activity_task
                        monitor_task.cancel()
                    except ActivityError as e:
                        print(f"ActivityError {e=}")

                        # Cancel both tasks
                        build_image_activity_task.cancel()
                        monitor_task.cancel()

                        if (
                            is_cancelled_exception(e)
                            and self.cancellation_requested == deployment.hash
                        ):
                            return await self.handle_cancellation(
                                deployment,
                                last_completed_step=GitDeploymentStep.BUILDING_IMAGE,
                            )
                        raise  # reraise the same exception

                    if await check_for_cancellation(GitDeploymentStep.IMAGE_BUILT):
                        return await self.handle_cancellation(
                            deployment,
                            GitDeploymentStep.IMAGE_BUILT,
                        )
                    if self.image_built is None:
                        deployment_status = Deployment.DeploymentStatus.FAILED
                        deployment_status_reason = "Failed to build the image"
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

                        if await check_for_cancellation(
                            GitDeploymentStep.VOLUMES_CREATED
                        ):
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

                        if await check_for_cancellation(
                            GitDeploymentStep.CONFIGS_CREATED
                        ):
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
            print(f"ActivityError({e=}) !")
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
                    GitCloneDetails(
                        deployment=deployment,
                        tmp_dir=self.tmp_dir,
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
        print(f"cancelling at {last_completed_step=}")
        previous_production_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_production_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

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
    async def run(self, service: ArchivedDockerServiceDetails):
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


@workflow.defn(name="archive-git-service-workflow")
class ArchiveGitServiceWorkflow:
    @workflow.run
    async def run(self, service: ArchivedGitServiceDetails):
        print(f"\nRunning workflow `ArchiveGitServiceWorkflow` with {service=}")
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
