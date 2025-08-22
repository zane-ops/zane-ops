from temporalio import workflow
from .system import *
from .environments import *
from .services import *
from .projects import *

with workflow.unsafe.imports_passed_through():

    from ..activities import (
        DockerSwarmActivities,
        SystemCleanupActivities,
        GitActivities,
        delete_env_resources,
        acquire_deploy_semaphore,
        release_deploy_semaphore,
        lock_deploy_semaphore,
        reset_deploy_semaphore,
    )
    from ..activities.service_auto_update import (
        update_docker_service,
        update_image_version_in_env_file,
    )
    from . import (
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
        DelayedArchiveEnvWorkflow,
    )
    from ..schedules import (
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
            DelayedArchiveEnvWorkflow,
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
            swarm_activities.set_cancelling_status,
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
            delete_env_resources,
        ],
    )
