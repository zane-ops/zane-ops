import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy


from temporalio.exceptions import ActivityError, is_cancelled_exception
from temporalio.workflow import ActivityHandle

with workflow.unsafe.imports_passed_through():
    from ..activities import ComposeStackActivities
    from ..shared import (
        ComposeStackDeploymentDetails,
        ComposeStackBuildDetails,
        ComposeStackMonitorPayload,
        ComposeStackArchiveDetails,
        ComposeStackArchiveResult,
        CancelDeploymentSignalInput,
        ToggleComposeStackDetails,
    )
    from compose.models import ComposeStackDeployment


@workflow.defn(name="deploy-compose-stack")
class DeployComposeStackWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )
        self.cancellation_requested: set[str] = set()

    @workflow.signal
    async def cancel(self, input: CancelDeploymentSignalInput):
        self.cancellation_requested.add(input.deployment_hash)
        print(f"Received signal {input=} {self.cancellation_requested=}")

    def check_for_cancellation(self, deployment: ComposeStackDeploymentDetails) -> bool:
        return deployment.hash in self.cancellation_requested

    async def monitor_cancellation(
        self,
        activity_handle: ActivityHandle,
        deployment: ComposeStackDeploymentDetails,
        timeout: timedelta = timedelta(seconds=30),
    ):
        """
        Monitor for cancellation requests during long-running activities.
        If cancellation is requested, cancel the activity.
        """
        try:
            await workflow.wait_condition(
                lambda: deployment.hash in self.cancellation_requested,
                timeout=timeout,
            )
        except (asyncio.CancelledError, TimeoutError):
            pass  # do nothing
        else:
            activity_handle.cancel()

    async def handle_cancellation(
        self,
        deployment: ComposeStackDeploymentDetails,
        build_details: Optional[ComposeStackBuildDetails] = None,
    ) -> Optional[ComposeStackDeploymentDetails]:
        print(f"Handling cancellation for deployment {deployment.hash}")

        if build_details is not None:
            await workflow.execute_activity_method(
                ComposeStackActivities.cleanup_temporary_directory_for_stack_deployment,
                build_details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

        await workflow.execute_activity_method(
            ComposeStackActivities.save_cancelled_stack_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            ComposeStackActivities.reset_stack_deploy_semaphore,
            deployment.stack.id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        next_queued_deployment = await workflow.execute_activity_method(
            ComposeStackActivities.get_next_queued_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=self.retry_policy,
        )
        if next_queued_deployment is not None:
            workflow.continue_as_new(next_queued_deployment)
        return next_queued_deployment

    @workflow.run
    async def run(self, deployment: ComposeStackDeploymentDetails):
        print(f"Running workflow DeployComposeStackWorkflow.run({deployment=})")

        build_details: ComposeStackBuildDetails | None = None
        status, status_reason = (
            ComposeStackDeployment.DeploymentStatus.FAILED,
            "Deployment failed",
        )

        await workflow.execute_activity_method(
            ComposeStackActivities.lock_stack_deploy_semaphore,
            deployment.stack.id,
            start_to_close_timeout=timedelta(minutes=7),
            retry_policy=self.retry_policy,
        )

        if self.check_for_cancellation(deployment):
            return await self.handle_cancellation(deployment, build_details)

        try:
            await workflow.execute_activity_method(
                ComposeStackActivities.prepare_stack_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            if self.check_for_cancellation(deployment):
                return await self.handle_cancellation(deployment, build_details)

            tmp_dir = await workflow.execute_activity_method(
                ComposeStackActivities.create_temporary_directory_for_stack_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            build_details = ComposeStackBuildDetails(
                tmp_build_dir=tmp_dir, deployment=deployment
            )

            if self.check_for_cancellation(deployment):
                return await self.handle_cancellation(deployment, build_details)

            await workflow.execute_activity_method(
                ComposeStackActivities.create_files_in_docker_stack_folder,
                build_details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            if self.check_for_cancellation(deployment):
                return await self.handle_cancellation(deployment, build_details)

            deploy_activity_handle = workflow.start_activity_method(
                ComposeStackActivities.deploy_stack_with_cli,
                build_details,
                start_to_close_timeout=timedelta(minutes=2, seconds=30),
                heartbeat_timeout=timedelta(seconds=3),
                retry_policy=self.retry_policy,
            )
            monitor_task = asyncio.create_task(
                self.monitor_cancellation(
                    deploy_activity_handle,
                    deployment,
                    timeout=timedelta(minutes=2, seconds=30),
                )
            )

            try:
                await deploy_activity_handle
                monitor_task.cancel()
            except ActivityError as e:
                deploy_activity_handle.cancel()
                monitor_task.cancel()
                if (
                    is_cancelled_exception(e)
                    and deployment.hash in self.cancellation_requested
                ):
                    return await self.handle_cancellation(deployment, build_details)
                raise

            if self.check_for_cancellation(deployment):
                return await self.handle_cancellation(deployment, build_details)

            healthcheck_activity_handle = workflow.start_activity_method(
                ComposeStackActivities.check_stack_health,
                deployment,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=timedelta(seconds=3),
                retry_policy=self.retry_policy,
            )
            monitor_task = asyncio.create_task(
                self.monitor_cancellation(
                    healthcheck_activity_handle,
                    deployment,
                    timeout=timedelta(minutes=2),
                )
            )

            try:
                status, status_reason = await healthcheck_activity_handle
                monitor_task.cancel()
            except ActivityError as e:
                healthcheck_activity_handle.cancel()
                monitor_task.cancel()
                if (
                    is_cancelled_exception(e)
                    and deployment.hash in self.cancellation_requested
                ):
                    return await self.handle_cancellation(deployment, build_details)
                raise

            await workflow.execute_activity_method(
                ComposeStackActivities.expose_stack_services_to_http,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            await workflow.execute_activity_method(
                ComposeStackActivities.create_stack_healthcheck_schedule,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                ComposeStackActivities.cleanup_old_stack_urls,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                ComposeStackActivities.cleanup_old_stack_services,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

        finally:
            if not self.check_for_cancellation(deployment):
                if build_details is not None:
                    await workflow.execute_activity_method(
                        ComposeStackActivities.cleanup_temporary_directory_for_stack_deployment,
                        build_details,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )

                await workflow.execute_activity_method(
                    ComposeStackActivities.finalize_stack_deployment,
                    ComposeStackMonitorPayload(
                        status,
                        status_reason,
                        deployment=deployment,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
                await workflow.execute_activity_method(
                    ComposeStackActivities.reset_stack_deploy_semaphore,
                    deployment.stack.id,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

                next_queued_deployment = await workflow.execute_activity_method(
                    ComposeStackActivities.get_next_queued_deployment,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=self.retry_policy,
                )
                if next_queued_deployment is not None:
                    workflow.continue_as_new(next_queued_deployment)
                return next_queued_deployment


@workflow.defn(name="archive-compose-stack")
class ArchiveComposeStackWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, details: ComposeStackArchiveDetails):
        print(f"Running workflow ArchiveComposeStackWorkflow.run({details=})")

        await workflow.execute_activity_method(
            ComposeStackActivities.lock_stack_deploy_semaphore,
            details.stack.id,
            start_to_close_timeout=timedelta(minutes=7),
            retry_policy=self.retry_policy,
        )

        try:
            deleted_routes = await workflow.execute_activity_method(
                ComposeStackActivities.unexpose_stack_services_from_http,
                details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                ComposeStackActivities.delete_stack_healthcheck_schedule,
                details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            services = await workflow.execute_activity_method(
                ComposeStackActivities.get_services_in_stack,
                details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            result = ComposeStackArchiveResult(
                services_deleted=services,
                routes_removed=deleted_routes,
            )

            await workflow.execute_activity_method(
                ComposeStackActivities.remove_stack_with_cli,
                details,
                start_to_close_timeout=timedelta(minutes=2, seconds=30),
                retry_policy=self.retry_policy,
            )

            await asyncio.gather(
                *[
                    workflow.execute_activity_method(
                        ComposeStackActivities.wait_for_stack_service_containers_to_be_deleted,
                        service,
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=self.retry_policy,
                    )
                    for service in services
                ]
            )

            result.config_deleted = await workflow.execute_activity_method(
                ComposeStackActivities.delete_stack_configs,
                details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            result.volumes_deleted = await workflow.execute_activity_method(
                ComposeStackActivities.delete_stack_volumes,
                details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
        except Exception:
            pass  # do nothing
        else:
            return result
        finally:
            await workflow.execute_activity_method(
                ComposeStackActivities.reset_stack_deploy_semaphore,
                details.stack.id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )


@workflow.defn(name="toggle-compose-stack-state")
class ToggleComposeStackWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, details: ToggleComposeStackDetails):
        print(f"Running workflow ToggleComposeStackWorkflow.run({details=})")

        await workflow.execute_activity_method(
            ComposeStackActivities.lock_stack_deploy_semaphore,
            details.stack.id,
            start_to_close_timeout=timedelta(minutes=7),
            retry_policy=self.retry_policy,
        )

        try:
            if details.desired_state == "stop":
                await workflow.execute_activity_method(
                    ComposeStackActivities.scale_down_stack_services,
                    details,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=self.retry_policy,
                )

            else:
                await workflow.execute_activity_method(
                    ComposeStackActivities.scale_up_stack_services,
                    details,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=self.retry_policy,
                )
        finally:
            await workflow.execute_activity_method(
                ComposeStackActivities.reset_stack_deploy_semaphore,
                details.stack.id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
