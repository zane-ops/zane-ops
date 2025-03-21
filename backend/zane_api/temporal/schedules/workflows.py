from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from .activities import (
    DockerDeploymentStatsActivities,
    MonitorDockerDeploymentActivities,
    CleanupActivities,
)
from ..shared import (
    HealthcheckDeploymentDetails,
    DeploymentHealthcheckResult,
    CleanupResult,
    SimpleDeploymentDetails,
)

with workflow.unsafe.imports_passed_through():
    from django.conf import settings
    from ...models import Deployment


@workflow.defn(name="monitor-docker-deployment-workflow")
class MonitorDockerDeploymentWorkflow:
    @workflow.run
    async def run(self, payload: HealthcheckDeploymentDetails):
        print(f"\nRunning workflow MonitorDockerDeploymentWorkflow with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )
        print("Running activity `monitor_close_faulty_db_connections()`")
        await workflow.execute_activity_method(
            MonitorDockerDeploymentActivities.monitor_close_faulty_db_connections,
            retry_policy=retry_policy,
            start_to_close_timeout=timedelta(seconds=10),
        )

        print(f"Running activity `run_deployment_monitor_healthcheck({payload=})`")
        healthcheck_timeout = (
            payload.healthcheck.timeout_seconds
            if payload.healthcheck is not None
            else settings.DEFAULT_HEALTHCHECK_TIMEOUT
        )
        deployment_status, deployment_status_reason = (
            await workflow.execute_activity_method(
                MonitorDockerDeploymentActivities.run_deployment_monitor_healthcheck,
                payload,
                retry_policy=retry_policy,
                start_to_close_timeout=timedelta(seconds=healthcheck_timeout + 5),
            )
        )

        # Do not run healthcheck if deployment is sleeping
        if deployment_status == Deployment.DeploymentStatus.SLEEPING:
            return deployment_status, deployment_status_reason

        healthcheck_result = DeploymentHealthcheckResult(
            deployment_hash=payload.deployment.hash,
            status=deployment_status,
            reason=deployment_status_reason,
            service_id=payload.deployment.service_id,
        )
        print(
            f"Running activity `save_deployment_status({healthcheck_result.status=})`"
        )
        await workflow.execute_activity_method(
            MonitorDockerDeploymentActivities.save_deployment_status,
            healthcheck_result,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )
        return deployment_status, deployment_status_reason


@workflow.defn(name="get-docker-deployment-stats")
class GetDockerDeploymentStatsWorkflow:
    @workflow.run
    async def run(self, payload: SimpleDeploymentDetails):
        print(f"\nRunning workflow GetDockerDeploymentStatsWorkflow with {payload=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )
        print("Running activity `monitor_close_faulty_db_connections()`")
        await workflow.execute_activity_method(
            MonitorDockerDeploymentActivities.monitor_close_faulty_db_connections,
            retry_policy=retry_policy,
            start_to_close_timeout=timedelta(seconds=10),
        )

        print("Running activity `get_deployment_stats()`")
        metrics_result = await workflow.execute_activity_method(
            DockerDeploymentStatsActivities.get_deployment_stats,
            payload,
            retry_policy=retry_policy,
            start_to_close_timeout=timedelta(seconds=30),
        )

        if metrics_result:
            print(f"Running activity `save_deployment_stats({metrics_result=})`")
            await workflow.execute_activity_method(
                DockerDeploymentStatsActivities.save_deployment_stats,
                metrics_result,
                retry_policy=retry_policy,
                start_to_close_timeout=timedelta(seconds=30),
            )

        return metrics_result


@workflow.defn(name="cleanup-app-logs")
class CleanupAppLogsWorkflow:
    @workflow.run
    async def run(self) -> CleanupResult:
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )
        result = await workflow.execute_activity_method(
            CleanupActivities.cleanup_service_metrics,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        return result
