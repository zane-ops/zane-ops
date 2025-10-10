import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from ..shared import UpdateDetails, UpdateOnGoingDetails


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        SystemCleanupActivities,
    )

    from ..activities import (
        lock_deploy_semaphore,
        reset_deploy_semaphore,
    )
    from ..activities.service_auto_update import (
        schedule_update_docker_service,
        update_image_version_in_env_file,
        wait_for_service_to_be_updated,
        update_ongoing_state,
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
            ("zane_proxy", "ghcr.io/zane-ops/proxy", False),
            ("zane_app", "ghcr.io/zane-ops/app", True),
            ("zane_temporal-schedule-worker", "ghcr.io/zane-ops/app", True),
            ("zane_temporal-main-worker", "ghcr.io/zane-ops/app", True),
        ]

        for service, image, _ in services_to_update:
            print(
                f"Running activity `update_docker_service({service=}, {desired_version=})`"
            )
            await workflow.execute_activity(
                schedule_update_docker_service,
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
            update_ongoing_state,
            UpdateOnGoingDetails(ongoing=True),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        try:
            await asyncio.gather(
                *[
                    workflow.execute_activity(
                        wait_for_service_to_be_updated,
                        UpdateDetails(
                            service_name=service,
                            desired_version=desired_version,
                            service_image=image,
                            wait_for_update=wait_for_update,
                        ),
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=retry_policy,
                    )
                    for service, image, wait_for_update in services_to_update
                ]
            )
        finally:
            await workflow.execute_activity(
                update_ongoing_state,
                UpdateOnGoingDetails(ongoing=False),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

        await workflow.execute_activity(
            update_image_version_in_env_file,
            desired_version,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )
