from datetime import timedelta
from typing import Any, Awaitable, Callable, Union

import temporalio.common
from temporalio import workflow
from temporalio.service import RPCError


from temporalio.client import (
    Client,
    WorkflowHandle,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleIntervalSpec,
)
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.types import (
    MethodAsyncNoParam,
    MethodAsyncSingleParam,
    ReturnType,
    SelfType,
)

with workflow.unsafe.imports_passed_through():
    from asgiref.sync import async_to_sync
    from django.conf import settings

    from .activities import (
        DockerSwarmActivities,
        SystemCleanupActivities,
        GitActivities,
    )
    from .activities import (
        acquire_deploy_semaphore,
        release_deploy_semaphore,
        lock_deploy_semaphore,
        reset_deploy_semaphore,
    )
    from .activities.service_auto_update import (
        update_docker_service,
        update_image_version_in_env_file,
    )
    from .workflows import (
        ArchiveDockerServiceWorkflow,
        SystemCleanupWorkflow,
        CreateProjectResourcesWorkflow,
        RemoveProjectResourcesWorkflow,
        DeployDockerServiceWorkflow,
        ToggleDockerServiceWorkflow,
        AutoUpdateDockerServiceWorkflow,
        CreateEnvNetworkWorkflow,
        ArchiveEnvWorkflow,
        DeployGitServiceWorkflow,
        ArchiveGitServiceWorkflow,
    )
    from .schedules import (
        MonitorDockerDeploymentWorkflow,
        MonitorDockerDeploymentActivities,
        CleanupActivities,
        CleanupAppLogsWorkflow,
        DockerDeploymentStatsActivities,
        GetDockerDeploymentStatsWorkflow,
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
            ArchiveGitServiceWorkflow,
        ],
        activities=[
            git_activities.create_temporary_directory_for_build,
            git_activities.create_buildkit_builder_for_env,
            git_activities.delete_buildkit_builder_for_env,
            git_activities.cleanup_temporary_directory_for_build,
            git_activities.clone_repository_and_checkout_to_commit,
            git_activities.update_deployment_commit_message_and_author,
            git_activities.build_service_with_dockerfile,
            git_activities.generate_default_files_for_dockerfile_builder,
            git_activities.generate_default_files_for_static_builder,
            git_activities.generate_default_files_for_nixpacks_builder,
            git_activities.generate_default_files_for_railpack_builder,
            git_activities.build_service_with_railpack_dockerfile,
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
            swarm_activities.remove_project_networks,
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


async def get_temporalio_client():
    return await Client.connect(
        settings.TEMPORALIO_SERVER_URL, namespace=settings.TEMPORALIO_WORKER_NAMESPACE
    )


async def create_schedule(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: Any,
    id: str,
    interval: timedelta,
    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
):
    client = await get_temporalio_client()
    await client.create_schedule(
        f"schedule-{id}",
        Schedule(
            action=ScheduleActionStartWorkflow(
                workflow=workflow,
                arg=args,
                id=id,
                task_queue=task_queue,
                execution_timeout=execution_timeout,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=interval)]),
        ),
    )


async def pause_schedule(id: str, note: str | None = None):
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )

    await handle.pause(note=note)


async def unpause_schedule(id: str, note: str | None = None):
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )

    await handle.unpause(note=note)


async def delete_schedule(id: str):
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )
    await handle.delete()


@async_to_sync
async def start_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    arg: Any,
    id: str,
    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    retry_policy=RetryPolicy(
        maximum_attempts=1,
    ),
) -> WorkflowHandle:
    client = await get_temporalio_client()
    try:
        await client.start_workflow(
            workflow=workflow,
            arg=arg,
            id=id,
            task_queue=task_queue,
            retry_policy=retry_policy,
            execution_timeout=execution_timeout,
        )
    except WorkflowAlreadyStartedError:
        pass

    return client.get_workflow_handle(id)


@async_to_sync
async def workflow_signal(
    workflow: Union[
        MethodAsyncNoParam[SelfType, ReturnType],
        MethodAsyncSingleParam[SelfType, Any, ReturnType],
    ],
    workflow_id: str,
    signal: Union[str, Callable[..., Awaitable[Any]]],
    arg: Any = temporalio.common._arg_unset,
    timeout: timedelta = timedelta(seconds=5),
):
    client = await get_temporalio_client()
    workflow_handle = client.get_workflow_handle_for(
        workflow=workflow, workflow_id=workflow_id
    )
    try:
        await workflow_handle.signal(
            signal,
            arg=arg,
            rpc_timeout=timeout,
        )
    except RPCError:
        # probably because the signal sent to the workflow could not be executed
        pass
