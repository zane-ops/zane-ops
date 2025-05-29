from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from ..shared import (
    UpdateDetails,
)


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        SystemCleanupActivities,
    )

    from ..activities import (
        lock_deploy_semaphore,
        reset_deploy_semaphore,
    )
    from ..activities.service_auto_update import (
        update_docker_service,
        update_image_version_in_env_file,
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
