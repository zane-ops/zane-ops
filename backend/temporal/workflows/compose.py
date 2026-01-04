from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import ComposeStackActivities
    from ..shared import (
        ComposeStackDeploymentDetails,
        ComposeStackBuildDetails,
        ComposeStackMonitorPayload,
    )
    from compose.models import ComposeStackDeployment


@workflow.defn(name="deploy-compose-stack")
class DeployComposeStackWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, deployment: ComposeStackDeploymentDetails):
        print(f"Running workflow DeployComposeStackWorkflow.run({deployment=})")

        build_details: ComposeStackBuildDetails | None = None
        status, status_reason = (
            ComposeStackDeployment.DeploymentStatus.FAILED,
            "Deployment failed",
        )
        try:
            await workflow.execute_activity_method(
                ComposeStackActivities.prepare_stack_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            tmp_dir = await workflow.execute_activity_method(
                ComposeStackActivities.create_temporary_directory_for_stack_deployment,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            build_details = ComposeStackBuildDetails(
                tmp_build_dir=tmp_dir, deployment=deployment
            )

            await workflow.execute_activity_method(
                ComposeStackActivities.create_files_in_docker_stack_folder,
                build_details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await workflow.execute_activity_method(
                ComposeStackActivities.deploy_stack_with_cli,
                build_details,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            status, status_reason = await workflow.execute_activity_method(
                ComposeStackActivities.monitor_stack_health,
                deployment,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=timedelta(seconds=3),
                retry_policy=self.retry_policy,
            )

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

        finally:
            if build_details is not None:
                await workflow.execute_activity_method(
                    ComposeStackActivities.cleanup_temporary_directory_for_stack_deployment,
                    build_details,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

            await workflow.execute_activity_method(
                ComposeStackActivities.finalize_deployment,
                ComposeStackMonitorPayload(
                    status,
                    status_reason,
                    deployment=deployment,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
