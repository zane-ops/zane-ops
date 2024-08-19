import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from .shared import (
    DeploymentHealthcheckResult,
    SimpleDeploymentDetails,
    ArchivedServiceDetails,
)

with workflow.unsafe.imports_passed_through():
    from ..models import DockerDeployment
    from .activities import DockerSwarmActivities
    from .shared import ProjectDetails, ArchivedProjectDetails, DeploymentDetails
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


@workflow.defn(name="deploy-docker-service-workflow")
class DeployDockerServiceWorkflow:
    @workflow.run
    async def run(self, deployment: DeploymentDetails):
        print(f"\nRunning workflow `DeployDockerServiceWorkflow` with {deployment=}")
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

        print(f"Running activity `prepare_deployment({deployment=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.prepare_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        print(f"Running activity `get_previous_production_deployment({deployment=})`")
        previous_production_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_production_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        service = deployment.service
        if len(service.docker_volumes) > 0:
            print(
                f"Running activity `create_docker_volumes_for_service({deployment=})`"
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.create_docker_volumes_for_service,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

        if (
            len(service.volumes) > 0 or len(service.non_http_ports) > 0
        ) and previous_production_deployment is not None:
            print(
                f"Running activity `scale_down_service_deployment({previous_production_deployment=})`"
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_service_deployment,
                previous_production_deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )

        print(
            f"Running activity `create_swarm_service_for_docker_deployment({deployment=})`"
        )
        await workflow.execute_activity_method(
            DockerSwarmActivities.create_swarm_service_for_docker_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        if deployment.service.http_port is not None:
            print(
                f"Running activity `expose_docker_service_deployment_to_http({deployment=})`"
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.expose_docker_service_deployment_to_http,
                deployment,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

        print(f"Running activity `run_deployment_healthcheck({deployment=})`")
        healthcheck_timeout = (
            deployment.service.healthcheck.timeout_seconds
            if deployment.service.healthcheck is not None
            else settings.DEFAULT_HEALTHCHECK_TIMEOUT
        )
        deployment_status, deployment_status_reason = (
            await workflow.execute_activity_method(
                DockerSwarmActivities.run_deployment_healthcheck,
                deployment,
                retry_policy=retry_policy,
                start_to_close_timeout=timedelta(seconds=healthcheck_timeout + 5),
            )
        )

        if deployment_status == DockerDeployment.DeploymentStatus.HEALTHY:
            if deployment.service.http_port is not None:
                print(
                    f"Running activity `expose_docker_service_to_http({deployment=})`"
                )
                await workflow.execute_activity_method(
                    DockerSwarmActivities.expose_docker_service_to_http,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

        healthcheck_result = DeploymentHealthcheckResult(
            deployment_hash=deployment.hash,
            status=deployment_status,
            reason=deployment_status_reason,
        )
        print(f"Running activity `finish_and_save_deployment({healthcheck_result=})`")
        await workflow.execute_activity_method(
            DockerSwarmActivities.finish_and_save_deployment,
            healthcheck_result,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        if healthcheck_result.status == DockerDeployment.DeploymentStatus.HEALTHY:
            if previous_production_deployment is not None:
                print(
                    f"Running activity `scale_down_and_remove_docker_service_deployment({previous_production_deployment=})`"
                )
                await workflow.execute_activity_method(
                    DockerSwarmActivities.scale_down_and_remove_docker_service_deployment,
                    previous_production_deployment,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )

                print(f"Running activity `remove_old_docker_volumes({deployment=})`")
                await workflow.execute_activity_method(
                    DockerSwarmActivities.remove_old_docker_volumes,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

                print(f"Running activity `remove_old_urls({deployment=})`")
                await workflow.execute_activity_method(
                    DockerSwarmActivities.remove_old_urls,
                    deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

                print(
                    f"Running activity `cleanup_previous_deployment({previous_production_deployment=})`"
                )
                await workflow.execute_activity_method(
                    DockerSwarmActivities.cleanup_previous_production_deployment,
                    previous_production_deployment,
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=retry_policy,
                )

            print(
                f"Running activity `create_deployment_healthcheck_schedule({deployment=})`"
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.create_deployment_healthcheck_schedule,
                deployment,
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=retry_policy,
            )
        else:
            current_deployment = SimpleDeploymentDetails(
                hash=deployment.hash,
                project_id=deployment.service.project_id,
                service_id=deployment.service.id,
            )
            print(
                f"Running activity `scale_down_and_remove_docker_service_deployment({current_deployment=})`"
            )
            await workflow.execute_activity_method(
                DockerSwarmActivities.scale_down_and_remove_docker_service_deployment,
                current_deployment,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )
            if previous_production_deployment is not None:
                print(
                    f"Running activity `scale_back_service_deployment({previous_production_deployment=})`"
                )
                await workflow.execute_activity_method(
                    DockerSwarmActivities.scale_back_service_deployment,
                    previous_production_deployment,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

        print(f"Running activity `get_previous_queued_deployment({deployment=})`")
        next_queued_deployment = await workflow.execute_activity_method(
            DockerSwarmActivities.get_previous_queued_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )
        if next_queued_deployment is not None:
            print(f"{next_queued_deployment=}")
            await workflow.continue_as_new(next_queued_deployment)
        return dict(
            healthcheck_result=healthcheck_result,
            next_queued_deployment=next_queued_deployment,
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
        ],
        activities=[
            swarm_activities.attach_network_to_proxy,
            swarm_activities.create_project_network,
            swarm_activities.unexpose_docker_service_from_http,
            swarm_activities.detach_network_from_proxy,
            swarm_activities.remove_project_network,
            swarm_activities.cleanup_docker_service_resources,
            swarm_activities.get_archived_project_services,
            swarm_activities.prepare_deployment,
            swarm_activities.scale_down_service_deployment,
            swarm_activities.create_docker_volumes_for_service,
            swarm_activities.create_swarm_service_for_docker_deployment,
            swarm_activities.run_deployment_healthcheck,
            swarm_activities.expose_docker_service_deployment_to_http,
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
