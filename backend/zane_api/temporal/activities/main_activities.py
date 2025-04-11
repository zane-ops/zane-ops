import asyncio
import json
from datetime import timedelta
import re
from typing import Any, Coroutine, List, Optional, TypedDict

from rest_framework import status
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError
from temporalio.client import ScheduleAlreadyRunningError


import platform
from ..main import create_schedule, delete_schedule, pause_schedule, unpause_schedule

with workflow.unsafe.imports_passed_through():
    from ..schedules import (
        MonitorDockerDeploymentWorkflow,
        GetDockerDeploymentStatsWorkflow,
    )
    from search.loki_client import LokiSearchClient
    import docker
    import docker.errors
    from ...models import (
        Project,
        ArchivedProject,
        ArchivedDockerService,
        ArchivedGitService,
        Deployment,
        HealthCheck,
        DeploymentChange,
    )
    from docker.models.services import Service
    from urllib3.exceptions import HTTPError
    from requests import RequestException
    import requests
    from docker.types import (
        EndpointSpec,
        NetworkAttachmentConfig,
        RestartPolicy,
        Resources,
        UpdateConfig,
        ConfigReference,
        Healthcheck as DockerHealthcheckType,
    )
    from django.conf import settings
    from django.utils import timezone
    from time import monotonic
    from django.db.models import Q, Case, When, Value, F
    from ...utils import (
        find_item_in_list,
        format_seconds,
        DockerSwarmTask,
        DockerSwarmTaskState,
        Colors,
        convert_value_to_bytes,
    )
    from ..semaphore import AsyncSemaphore
    from ..helpers import (
        deployment_log,
        ZaneProxyClient,
        get_docker_client,
        get_config_resource_name,
        get_env_network_resource_name,
        get_network_resource_name,
        get_resource_labels,
        get_swarm_service_name_for_deployment,
        get_volume_resource_name,
        replace_placeholders,
    )

from ...dtos import (
    ConfigDto,
    DockerServiceSnapshot,
    URLDto,
    HealthCheckDto,
    VolumeDto,
)
from ..shared import (
    ArchivedGitServiceDetails,
    DeploymentCreateConfigsResult,
    ProjectDetails,
    EnvironmentDetails,
    ArchivedProjectDetails,
    ArchivedDockerServiceDetails,
    SimpleDeploymentDetails,
    DeploymentDetails,
    DeploymentHealthcheckResult,
    HealthcheckDeploymentDetails,
    DeploymentCreateVolumesResult,
    SimpleGitDeploymentDetails,
)


DEPLOY_SEMAPHORE_KEY = "deploy-workflow"


@activity.defn
async def acquire_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    )
    await semaphore.acquire()


@activity.defn
async def release_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    )
    await semaphore.release()


@activity.defn
async def lock_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=timedelta(
            minutes=5
        ),  # this is to prevent the system cleanup from blocking for too long
    )
    await semaphore.acquire_all()


@activity.defn
async def reset_deploy_semaphore():
    semaphore = AsyncSemaphore(
        key=DEPLOY_SEMAPHORE_KEY,
        limit=settings.TEMPORALIO_MAX_CONCURRENT_DEPLOYS,
        semaphore_timeout=timedelta(
            minutes=5
        ),  # this is to prevent the system cleanup from blocking for too long
    )
    await semaphore.reset()


class SystemCleanupActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def cleanup_images(self) -> dict:
        return self.docker_client.images.prune(
            filters={
                "dangling": False,
                "label!": ["zane-managed"],
            }
        )

    @activity.defn
    async def cleanup_volumes(self) -> dict:
        return self.docker_client.volumes.prune(
            filters={
                "all": True,
                "label!": ["zane-managed"],
            }
        )

    @activity.defn
    async def cleanup_containers(self) -> dict:
        return self.docker_client.containers.prune()

    @activity.defn
    async def cleanup_networks(self) -> dict:
        return self.docker_client.networks.prune(
            filters={
                "label!": ["zane-managed"],
            }
        )


class DockerSwarmActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def create_project_network(self, payload: ProjectDetails) -> str:
        try:
            project = await Project.objects.aget(id=payload.id)
        except Project.DoesNotExist:
            raise ApplicationError(
                f"Project with id=`{payload.id}` does not exist.", non_retryable=True
            )

        production_env = await project.aproduction_env
        network = self.docker_client.networks.create(
            name=get_env_network_resource_name(
                production_env.id, project_id=project.id
            ),
            scope="swarm",
            driver="overlay",
            labels=get_resource_labels(project.id, is_production="True"),
            attachable=True,
        )
        return network.id  # type:ignore

    @activity.defn
    async def create_environment_network(self, payload: EnvironmentDetails) -> str:
        network = self.docker_client.networks.create(
            name=get_env_network_resource_name(
                payload.id, project_id=payload.project_id
            ),
            scope="swarm",
            driver="overlay",
            labels=get_resource_labels(payload.project_id),
            attachable=True,
        )
        return network.id  # type:ignore

    @activity.defn
    async def delete_environment_network(self, payload: EnvironmentDetails):
        try:
            network = self.docker_client.networks.get(
                get_env_network_resource_name(payload.id, project_id=payload.project_id)
            )
        except docker.errors.NotFound:
            pass  # network has probably been already delete
        else:
            network.remove()

    @activity.defn
    async def get_archived_project_services(
        self, project_details: ArchivedProjectDetails
    ) -> List[ArchivedDockerServiceDetails | ArchivedGitServiceDetails]:
        try:
            archived_project: ArchivedProject = await ArchivedProject.objects.aget(
                pk=project_details.id
            )
        except ArchivedProject.DoesNotExist:
            raise ApplicationError(
                f"ArchivedProject with id=`{project_details.id}` does not exist.",
                non_retryable=True,
            )

        archived_docker_services = (
            ArchivedDockerService.objects.filter(project=archived_project)
            .select_related("project")
            .prefetch_related("volumes", "urls", "configs")
        )
        archived_git_services = (
            ArchivedGitService.objects.filter(project=archived_project)
            .select_related("project")
            .prefetch_related("volumes", "urls", "configs")
        )

        archived_services: List[
            ArchivedDockerServiceDetails | ArchivedGitServiceDetails
        ] = []
        async for service in archived_docker_services:
            archived_services.append(
                ArchivedDockerServiceDetails(
                    original_id=service.original_id,
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                            id=url.original_id,
                        )
                        for url in service.urls.all()
                    ],
                    project_id=archived_project.original_id,
                    deployments=[
                        SimpleDeploymentDetails(
                            hash=dpl.get("hash"),  # type: ignore
                            urls=dpl.get("urls") or [],  # type: ignore
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for dpl in service.deployments
                    ],
                )
            )
        async for service in archived_git_services:
            archived_services.append(
                ArchivedGitServiceDetails(
                    original_id=service.original_id,
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                            id=url.original_id,
                        )
                        for url in service.urls.all()
                    ],
                    project_id=service.project.original_id,
                    deployments=[
                        SimpleGitDeploymentDetails(
                            image_tag=dpl.get("image_tag"),  # type: ignore
                            commit_sha=dpl.get("commit_sha"),  # type: ignore
                            hash=dpl.get("hash"),  # type: ignore
                            urls=dpl.get("urls") or [],  # type: ignore
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for dpl in service.deployments
                    ],
                )
            )

        return archived_services

    @activity.defn
    async def get_archived_env_services(
        self, environment: EnvironmentDetails
    ) -> List[ArchivedDockerServiceDetails | ArchivedGitServiceDetails]:
        archived_docker_services = (
            ArchivedDockerService.objects.filter(environment_id=environment.id)
            .select_related("project")
            .prefetch_related("volumes", "urls", "configs")
        )
        archived_git_services = (
            ArchivedGitService.objects.filter(environment_id=environment.id)
            .select_related("project")
            .prefetch_related("volumes", "urls", "configs")
        )

        archived_services: List[
            ArchivedDockerServiceDetails | ArchivedGitServiceDetails
        ] = []
        async for service in archived_docker_services:
            archived_services.append(
                ArchivedDockerServiceDetails(
                    original_id=service.original_id,
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                            id=url.original_id,
                        )
                        for url in service.urls.all()
                    ],
                    project_id=service.project.original_id,
                    deployments=[
                        SimpleDeploymentDetails(
                            hash=dpl.get("hash"),  # type: ignore
                            urls=dpl.get("urls") or [],  # type: ignore
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for dpl in service.deployments
                    ],
                )
            )

        async for service in archived_git_services:
            archived_services.append(
                ArchivedGitServiceDetails(
                    original_id=service.original_id,
                    urls=[
                        URLDto(
                            domain=url.domain,
                            base_path=url.base_path,
                            strip_prefix=url.strip_prefix,
                            id=url.original_id,
                        )
                        for url in service.urls.all()
                    ],
                    project_id=service.project.original_id,
                    deployments=[
                        SimpleGitDeploymentDetails(
                            image_tag=dpl.get("image_tag"),  # type: ignore
                            commit_sha=dpl.get("commit_sha"),  # type: ignore
                            hash=dpl.get("hash"),  # type: ignore
                            urls=dpl.get("urls") or [],  # type: ignore
                            project_id=service.project.original_id,
                            service_id=service.original_id,
                        )
                        for dpl in service.deployments
                    ],
                )
            )

        return archived_services

    @activity.defn
    async def cleanup_docker_service_resources(
        self, service_details: ArchivedDockerServiceDetails | ArchivedGitServiceDetails
    ):
        for deployment in service_details.deployments:
            service_name = get_swarm_service_name_for_deployment(
                deployment_hash=deployment.hash,
                service_id=deployment.service_id,
                project_id=deployment.project_id,
            )
            try:
                swarm_service = self.docker_client.services.get(service_name)
            except docker.errors.NotFound:
                print(f"service `{service_name}` not found")
                # we will assume the service has already been deleted
                pass
            else:
                swarm_service.remove()

            async def wait_for_service_containers_to_be_removed():
                print(
                    f"waiting for containers for service {service_name=} to be removed..."
                )
                container_list = self.docker_client.containers.list(
                    filters={"name": service_name}
                )
                while len(container_list) > 0:
                    print(
                        f"service {service_name=} is not removed yet, "
                        + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    container_list = self.docker_client.containers.list(
                        filters={"name": service_name}
                    )
                    continue
                print(f"service {service_name=} is removed, YAY !! 🎉")

            await wait_for_service_containers_to_be_removed()

            print("Removed service. YAY !! 🎉")
            try:
                await asyncio.gather(
                    delete_schedule(deployment.monitor_schedule_id),
                    delete_schedule(deployment.metrics_schedule_id),
                )
            except RPCError:
                pass
        print("deleting volume list...")
        docker_volume_list = self.docker_client.volumes.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service_details.project_id,
                        parent=service_details.original_id,
                    ).items()
                ]
            }
        )

        for volume in docker_volume_list:
            volume.remove(force=True)
        print(f"Deleted {len(docker_volume_list)} volume(s), YAY !! 🎉")

        print("deleting config list...")
        docker_config_list = self.docker_client.configs.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service_details.project_id,
                        parent=service_details.original_id,
                    ).items()
                ]
            }
        )

        for config in docker_config_list:
            config.remove()
        print(f"Deleted {len(docker_config_list)} config(s), YAY !! 🎉")
        search_client = LokiSearchClient(
            host=settings.LOKI_HOST,
        )
        search_client.delete(
            query=dict(service_id=service_details.original_id),
        )

        # Here I wanted to use the condition `isinstance(service_details, ArchivedGitServiceDetails)`
        # But it does not work because the temporal decoder still serialize the data as the first type `ArchivedDockerServiceDetails`
        # So this condition is always false.
        # It doesn't cause any problem because if it's a docker service, the image list will return an empty list
        print("deleting image list...")
        docker_image_list = self.docker_client.images.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service_details.project_id,
                        parent=service_details.original_id,
                    ).items()
                ]
            }
        )
        for image in docker_image_list:
            image.remove(force=True)
        print(f"Deleted {len(docker_image_list)} images(s), YAY !! 🎉")

    @activity.defn
    async def remove_project_networks(
        self, project_details: ArchivedProjectDetails
    ) -> List[str]:
        networks_associated_to_project = self.docker_client.networks.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        project_id=project_details.original_id
                    ).items()
                ]
            }
        )

        deleted_networks: List[str] = [net.name for net in networks_associated_to_project]  # type: ignore
        for network in networks_associated_to_project:
            network.remove()
        return deleted_networks

    @activity.defn
    async def prepare_deployment(self, deployment: DeploymentDetails):
        try:
            await deployment_log(
                deployment,
                f"Preparing deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
            )
            docker_deployment: Deployment = await Deployment.objects.aget(
                hash=deployment.hash, service_id=deployment.service.id
            )
            if docker_deployment.status == Deployment.DeploymentStatus.QUEUED:
                docker_deployment.status = Deployment.DeploymentStatus.PREPARING
                docker_deployment.started_at = timezone.now()
                await docker_deployment.asave()
        except Deployment.DoesNotExist:
            raise ApplicationError(
                "Cannot execute a deploy on a non existent deployment.",
                non_retryable=True,
            )

    @activity.defn
    async def toggle_cancelling_status(self, deployment: DeploymentDetails):
        await deployment_log(
            deployment,
            f"Handling cancellation request for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        return await Deployment.objects.filter(hash=deployment.hash).aupdate(
            status=Deployment.DeploymentStatus.CANCELLING,
        )

    @activity.defn
    async def save_cancelled_deployment(self, deployment: DeploymentDetails):
        count = await Deployment.objects.filter(hash=deployment.hash).aupdate(
            status=Deployment.DeploymentStatus.CANCELLED,
            status_reason="Deployment cancelled.",
            finished_at=timezone.now(),
        )
        await deployment_log(
            deployment,
            f"Deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}"
            f" finished with status {Colors.GREY}{Deployment.DeploymentStatus.CANCELLED}{Colors.ENDC}.",
        )
        return count

    @activity.defn
    async def finish_and_save_deployment(
        self, healthcheck_result: DeploymentHealthcheckResult
    ) -> tuple[str, str]:
        try:
            deployment = (
                await Deployment.objects.filter(hash=healthcheck_result.deployment_hash)
                .select_related("service")
                .afirst()
            )

            if deployment is None:
                raise Deployment.DoesNotExist(
                    f"Docker deployment with hash='{healthcheck_result.deployment_hash}' does not exist."
                )

            deployment.status_reason = healthcheck_result.reason
            if (
                healthcheck_result.status == Deployment.DeploymentStatus.HEALTHY
                or await deployment.service.deployments.acount() == 1  # type: ignore
            ):
                deployment.is_current_production = True

            deployment.status = (
                Deployment.DeploymentStatus.HEALTHY
                if healthcheck_result.status == Deployment.DeploymentStatus.HEALTHY
                else Deployment.DeploymentStatus.FAILED
            )

            deployment.finished_at = timezone.now()
            await deployment.asave()

            if deployment.is_current_production:
                await deployment.service.deployments.filter(  # type: ignore
                    ~Q(hash=healthcheck_result.deployment_hash)
                ).aupdate(is_current_production=False)
                await deployment.service.deployments.filter(  # type: ignore
                    ~Q(hash=healthcheck_result.deployment_hash)
                    & Q(
                        status__in=[
                            Deployment.DeploymentStatus.PREPARING,
                            Deployment.DeploymentStatus.STARTING,
                            Deployment.DeploymentStatus.RESTARTING,
                        ]
                    )
                    & (Q(started_at__isnull=True) | Q(finished_at__isnull=True)),
                ).aupdate(
                    finished_at=Case(
                        When(finished_at__isnull=True, then=Value(timezone.now())),
                        default=F("finished_at"),
                    ),
                    started_at=Case(
                        When(started_at__isnull=True, then=Value(timezone.now())),
                        default=F("started_at"),
                    ),
                    status=Deployment.DeploymentStatus.REMOVED,
                )
        except Deployment.DoesNotExist:
            raise ApplicationError(
                "Cannot save a non existent deployment.",
                non_retryable=True,
            )
        else:
            status_color = (
                Colors.GREEN
                if deployment.status == Deployment.DeploymentStatus.HEALTHY
                else Colors.RED
            )
            await deployment_log(
                healthcheck_result,
                f"Deployment {Colors.ORANGE}{healthcheck_result.deployment_hash}{Colors.ENDC}"
                f" finished with status {status_color}{deployment.status}{Colors.ENDC}.",
            )
            await deployment_log(
                healthcheck_result,
                f"Deployment {Colors.ORANGE}{healthcheck_result.deployment_hash}{Colors.ENDC}"
                f" finished with reason {Colors.GREY}{deployment.status_reason}{Colors.ENDC}.",
            )
            return deployment.status, deployment.status_reason  # type: ignore

    @activity.defn
    async def get_previous_production_deployment(
        self, deployment: DeploymentDetails
    ) -> Optional[SimpleDeploymentDetails]:
        latest_production_deployment: Deployment | None = await (
            Deployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(is_current_production=True)
                & ~Q(hash=deployment.hash)
            )
            .order_by("-queued_at")
            .afirst()
        )

        if latest_production_deployment is not None:
            if (
                latest_production_deployment.service_snapshot.get("environment") is None  # type: ignore
            ):
                latest_production_deployment.service_snapshot["environment"] = (  # type: ignore
                    deployment.service.environment.to_dict()
                )
            return SimpleDeploymentDetails(
                hash=latest_production_deployment.hash,
                service_id=latest_production_deployment.service_id,  # type: ignore
                project_id=deployment.service.project_id,
                status=latest_production_deployment.status,
                urls=[url.domain async for url in latest_production_deployment.urls.all()],  # type: ignore
                service_snapshot=DockerServiceSnapshot.from_dict(
                    latest_production_deployment.service_snapshot  # type: ignore
                ),
            )
        return None

    @activity.defn
    async def get_previous_queued_deployment(self, deployment: DeploymentDetails):
        next_deployment = (
            await Deployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(status=Deployment.DeploymentStatus.QUEUED)
            )
            .select_related("service", "service__environment")
            .order_by("queued_at")
            .afirst()
        )

        if next_deployment is not None:
            latest_deployment = (
                await next_deployment.service.alatest_production_deployment
            )
            next_deployment.slot = Deployment.get_next_deployment_slot(
                latest_deployment
            )
            await next_deployment.asave()

            return await DeploymentDetails.afrom_deployment(deployment=next_deployment)
        return None

    @activity.defn
    async def delete_previous_production_deployment_schedules(
        self, deployment: SimpleDeploymentDetails
    ):
        docker_deployment = (
            await Deployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service_id
            )
            .select_related("service")
            .afirst()
        )

        if docker_deployment is not None:
            try:
                # delete schedule
                await asyncio.gather(
                    delete_schedule(
                        id=docker_deployment.monitor_schedule_id,
                    ),
                    delete_schedule(
                        id=docker_deployment.metrics_schedule_id,
                    ),
                )
                print(
                    f"Deleted previous production deployment schedules : {docker_deployment.hash=} {docker_deployment.monitor_schedule_id=} {docker_deployment.metrics_schedule_id=}"
                )
            except RPCError as e:
                print(f"Error deleting previous deployment schedules: {e}")
                # The schedule probably doesn't exist
                pass

    @activity.defn
    async def cleanup_previous_production_deployment(
        self, deployment: SimpleDeploymentDetails
    ):
        deployments = Deployment.objects.filter(hash=deployment.hash)

        await deployments.aupdate(
            status=Deployment.DeploymentStatus.REMOVED, is_current_production=False
        )
        return [dpl.hash async for dpl in deployments.all()]

    @activity.defn
    async def cleanup_previous_unclean_deployments(
        self, deployment: DeploymentDetails
    ) -> List[str]:
        # let's cleanup other deployments if they weren't cleaned up correctly
        previous_deployments = Deployment.objects.filter(
            Q(service_id=deployment.service.id)
            & Q(is_current_production=False)
            & ~Q(hash=deployment.hash)
            & ~Q(status=Deployment.DeploymentStatus.QUEUED)
            & ~Q(status=Deployment.DeploymentStatus.FAILED)
            & ~Q(status=Deployment.DeploymentStatus.REMOVED)
            & ~Q(status=Deployment.DeploymentStatus.CANCELLED)
        ).select_related("service", "service__project")

        deployments: List[Deployment] = []

        async for docker_deployment in previous_deployments:
            print(f"Found uncleaned deployment : {docker_deployment.hash=}")
            swarm_service_name = get_swarm_service_name_for_deployment(
                deployment_hash=docker_deployment.hash,
                project_id=docker_deployment.service.project.id,
                service_id=docker_deployment.service.id,
            )

            try:
                self.docker_client.services.get(swarm_service_name)
            except docker.errors.NotFound:
                # if the service hasn't been cleanup correctly
                deployments.append(docker_deployment)
            else:
                print(
                    f"Found rogue deployment : {docker_deployment.hash=} with service: {swarm_service_name=}"
                )

        jobs: List[Coroutine[Any, Any, None]] = []
        for docker_deployment in deployments:
            jobs.extend(
                [
                    delete_schedule(
                        id=docker_deployment.monitor_schedule_id,
                    ),
                    delete_schedule(
                        id=docker_deployment.metrics_schedule_id,
                    ),
                ]
            )
        try:
            # delete schedules
            await asyncio.gather(*jobs, return_exceptions=True)
        except RPCError:
            # The schedule probably doesn't exist
            pass

        await previous_deployments.aupdate(
            status=Deployment.DeploymentStatus.REMOVED,
            finished_at=Case(
                When(finished_at__isnull=True, then=Value(timezone.now()))
            ),
            started_at=Case(When(started_at__isnull=True, then=Value(timezone.now()))),
        )

        return [dpl.hash for dpl in deployments]

    @activity.defn
    async def create_docker_volumes_for_service(
        self, deployment: DeploymentDetails
    ) -> List[VolumeDto]:
        await deployment_log(
            deployment,
            f"Creating volumes for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        service = deployment.service
        created_volumes: List[VolumeDto] = []
        for volume in service.docker_volumes:
            try:
                self.docker_client.volumes.get(get_volume_resource_name(volume.id))  # type: ignore
            except docker.errors.NotFound:
                created_volumes.append(volume)
                self.docker_client.volumes.create(
                    name=get_volume_resource_name(volume.id),  # type: ignore
                    driver="local",
                    labels=get_resource_labels(service.project_id, parent=service.id),
                )

        await deployment_log(
            deployment,
            f"Volumes created succesfully for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}  ✅",
        )

        return created_volumes

    @activity.defn
    async def create_docker_configs_for_service(
        self, deployment: DeploymentDetails
    ) -> List[ConfigDto]:
        await deployment_log(
            deployment,
            f"Creating configuration files for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        service = deployment.service
        created_configs: List[ConfigDto] = []
        for config in service.configs:
            try:
                self.docker_client.configs.get(
                    get_config_resource_name(config.id, config.version)  # type: ignore
                )
            except docker.errors.NotFound:
                self.docker_client.configs.create(
                    name=get_config_resource_name(config.id, config.version),  # type: ignore
                    labels=get_resource_labels(service.project_id, parent=service.id),
                    data=config.contents.encode("utf-8"),
                )
                created_configs.append(config)

        await deployment_log(
            deployment,
            f"Configuration files created succesfully for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}  ✅",
        )

        return created_configs

    @activity.defn
    async def delete_created_volumes(self, deployment: DeploymentCreateVolumesResult):
        await deployment_log(
            deployment,
            f"Deleting created volumes for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}...",
        )
        for volume in deployment.created_volumes:
            try:
                docker_volume = self.docker_client.volumes.get(
                    get_volume_resource_name(volume.id)  # type: ignore
                )
            except docker.errors.NotFound:
                pass
            else:
                docker_volume.remove(force=True)

        await deployment_log(
            deployment,
            f"Volumes deleted succesfully for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}  ✅",
        )

    @activity.defn
    async def delete_created_configs(self, deployment: DeploymentCreateConfigsResult):
        await deployment_log(
            deployment,
            f"Deleting created config files for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}...",
        )
        for config in deployment.created_configs:
            try:
                docker_config = self.docker_client.configs.get(
                    get_config_resource_name(config.id, config.version)  # type: ignore
                )
            except docker.errors.NotFound:
                pass
            else:
                docker_config.remove()

        await deployment_log(
            deployment,
            f"Config files succesfully deleted for deployment {Colors.ORANGE}{deployment.deployment_hash}{Colors.ENDC}  ✅",
        )

    @activity.defn
    async def scale_down_service_deployment(self, deployment: SimpleDeploymentDetails):
        try:
            swarm_service: Service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.project_id,
                    service_id=deployment.service_id,
                )
            )
        except docker.errors.NotFound:
            # do nothing
            # The service for that deployment was removed probably
            return
        else:
            service_labels: dict = swarm_service.attrs["Spec"].get("Labels", {})
            service_labels["status"] = "sleeping"
            update_attributes = dict(
                mode={"Replicated": {"Replicas": 0}}, labels=service_labels
            )

            # This is to fix a bug with exposed ports conflicting with a new deployment, the
            # new deployment creates a service that needs the ports of the service to be available,
            # but it is still used by the old deployment.
            # To fix this we scale down and remove the ports from the old services
            # But only when the `service_snapshot` is provided because that mean we can reconstructs the open ports of the old deployment
            if deployment.service_snapshot is not None:
                update_attributes.update(endpoint_spec=EndpointSpec())

            swarm_service.update(**update_attributes)

            async def wait_for_service_to_be_down():
                print(f"waiting for service `{swarm_service.name=}` to be down...")
                task_list = swarm_service.tasks(filters={"desired-state": "running"})
                while len(task_list) > 0:
                    print(
                        f"service `{swarm_service.name=}` is not down yet, "
                        + f"retrying in `{settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL}` seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = swarm_service.tasks(
                        filters={"desired-state": "running"}
                    )
                print(f"service `{swarm_service.name=}` is down, YAY !! 🎉")

            await wait_for_service_to_be_down()
            # Change the status to be accurate
            docker_deployment = (
                await Deployment.objects.filter(
                    hash=deployment.hash, service_id=deployment.service_id
                )
                .select_related("service")
                .afirst()
            )

            if docker_deployment is not None:
                try:
                    await asyncio.gather(
                        pause_schedule(
                            id=docker_deployment.monitor_schedule_id,
                            note="Paused to prevent zero-downtime deployment",
                        ),
                        pause_schedule(
                            id=docker_deployment.metrics_schedule_id,
                            note="Paused to prevent zero-downtime deployment",
                        ),
                    )
                    print(f"Paused schedule {docker_deployment.monitor_schedule_id=}")
                except RPCError:
                    print(
                        f"Error pausing schedule {docker_deployment.monitor_schedule_id=}"
                    )
                    # The schedule probably doesn't exist
                    pass
                finally:
                    docker_deployment.status = Deployment.DeploymentStatus.SLEEPING
                    await docker_deployment.asave()

    @activity.defn
    async def scale_back_service_deployment(self, deployment: SimpleDeploymentDetails):
        try:
            swarm_service = self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.project_id,
                    service_id=deployment.service_id,
                )
            )
        except docker.errors.NotFound:
            # do nothing
            # The service for that deployment was removed probably
            return
        else:
            service_labels: dict = swarm_service.attrs["Spec"].get("Labels", {})
            service_labels["status"] = "active"
            update_attributes = dict(
                mode={"Replicated": {"Replicas": 1}}, labels=service_labels
            )

            # If we scaled this deployment by removing the port, we recreate the exposed ports
            if deployment.service_snapshot is not None:
                exposed_ports: dict[int, int] = {}
                new_endpoint_spec = EndpointSpec()

                # We don't expose HTTP ports with docker because they will be handled by caddy directly
                for port in deployment.service_snapshot.ports:
                    exposed_ports[port.host] = port.forwarded
                if len(exposed_ports) > 0:
                    new_endpoint_spec = EndpointSpec(ports=exposed_ports)
                update_attributes.update(endpoint_spec=new_endpoint_spec)

            swarm_service.update(**update_attributes)

            # Change back the status to be accurate
            docker_deployment: Deployment | None = (
                await Deployment.objects.filter(
                    Q(hash=deployment.hash)
                    & Q(service_id=deployment.service_id)
                    & Q(status=Deployment.DeploymentStatus.SLEEPING)
                )
                .select_related("service")
                .afirst()
            )

            if docker_deployment is not None:
                docker_deployment.status = Deployment.DeploymentStatus.STARTING
                await docker_deployment.asave()
                try:
                    await unpause_schedule(
                        id=docker_deployment.monitor_schedule_id,
                        note="Unpaused due to failed healthcheck",
                    )
                except RPCError:
                    # The schedule probably doesn't exist
                    pass

    @activity.defn
    async def pull_image_for_deployment(self, deployment: DeploymentDetails) -> bool:
        service = deployment.service
        await deployment_log(
            deployment,
            f"Pulling image {Colors.ORANGE}{service.image}{Colors.ENDC}...",
        )
        try:
            self.docker_client.images.pull(
                repository=service.image,  # type: ignore
                auth_config=(
                    service.credentials.to_dict()
                    if service.credentials is not None
                    else None
                ),
            )
        except docker.errors.ImageNotFound:
            await deployment_log(
                deployment,
                f"Error when pulling image {Colors.ORANGE}{service.image}{Colors.ENDC} {Colors.GREY}this image either does not exists for this platform (linux/{platform.machine()}) or may require credentials to pull ❌{Colors.ENDC}",
            )
            return False
        except docker.errors.APIError as e:
            await deployment_log(
                deployment,
                f"Error when pulling image {Colors.ORANGE}{service.image}{Colors.ENDC} {Colors.GREY}{e.explanation} ❌{Colors.ENDC}",
            )
            return False
        else:
            await deployment_log(
                deployment,
                f"Finished pulling image {Colors.ORANGE}{service.image}{Colors.ENDC} ✅",
            )
            return True

    @activity.defn
    async def create_swarm_service_for_docker_deployment(
        self, deployment: DeploymentDetails
    ):
        service = deployment.service

        try:
            self.docker_client.services.get(
                get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.service.project_id,
                    service_id=deployment.service.id,
                )
            )
        except docker.errors.NotFound:
            # add environment specific variables
            envs: list[str] = [
                f"{env.key}={env.value}" for env in service.environment.variables
            ]
            env_as_variables = {
                env.key: env.value for env in service.environment.variables
            }

            # then service variables, so that they overwrite the env specific variables
            for env in service.env_variables:
                value = replace_placeholders(env.value, env_as_variables, "env")
                envs.append(f"{env.key}={value}")

            # then zane-specific-envs
            for env in service.system_env_variables:
                value = replace_placeholders(
                    env.value,
                    {
                        "slot": deployment.slot,
                        "hash": deployment.hash,
                    },
                    "deployment",
                )
                envs.append(f"{env.key}={value}")

            # Volumes
            mounts: list[str] = []
            docker_volume_list = self.docker_client.volumes.list(
                filters={
                    "label": [
                        f"{key}={value}"
                        for key, value in get_resource_labels(
                            service.project_id, parent=service.id
                        ).items()
                    ]
                }
            )
            access_mode_map = {
                "READ_WRITE": "rw",
                "READ_ONLY": "ro",
            }

            for volume in service.docker_volumes:
                # Only include volumes that will not be deleted
                docker_volume = find_item_in_list(
                    lambda v: v.name == get_volume_resource_name(volume.id),  # type: ignore
                    docker_volume_list,
                )
                if docker_volume is not None:
                    mounts.append(
                        f"{docker_volume.name}:{volume.container_path}:{access_mode_map[volume.mode]}"
                    )
            for volume in service.host_volumes:
                mounts.append(
                    f"{volume.host_path}:{volume.container_path}:{access_mode_map[volume.mode]}"
                )

            # configs
            configs: list[ConfigReference] = []
            docker_config_list = self.docker_client.configs.list(
                filters={
                    "label": [
                        f"{key}={value}"
                        for key, value in get_resource_labels(
                            service.project_id, parent=service.id
                        ).items()
                    ]
                }
            )
            for config in service.configs:
                # Only include configs that will not be deleted
                docker_config = find_item_in_list(
                    lambda v: v.name
                    == get_config_resource_name(config.id, config.version),  # type: ignore
                    docker_config_list,
                )

                if docker_config is not None:
                    configs.append(
                        ConfigReference(
                            config_id=docker_config.id,
                            config_name=docker_config.name,
                            filename=config.mount_path,
                        )
                    )

            # ports
            exposed_ports: dict[int, int] = {}
            endpoint_spec: EndpointSpec | None = None

            # We don't expose HTTP ports with docker because they will be handled by caddy directly
            for port in service.ports:
                exposed_ports[port.host] = port.forwarded

            if len(exposed_ports) > 0:
                endpoint_spec = EndpointSpec(ports=exposed_ports)

            resources: Resources | None = None
            if service.resource_limits is not None:
                nano_cpus = None
                if service.resource_limits.cpus is not None:
                    nano_cpus = int(service.resource_limits.cpus * 1e9)
                mem_limit_in_bytes = None
                if service.resource_limits.memory is not None:
                    mem_limit_in_bytes = convert_value_to_bytes(
                        service.resource_limits.memory.value,
                        service.resource_limits.memory.unit,
                    )
                resources = Resources(
                    cpu_limit=nano_cpus,
                    mem_limit=mem_limit_in_bytes,
                )

            await deployment_log(
                deployment,
                f"Creating service for the deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
            )
            self.docker_client.services.create(
                image=(
                    service.image
                    if service.type == "DOCKER_REGISTRY"
                    else deployment.image_tag  # in case of `GIT_REPOSITORY`
                ),
                command=service.command,
                name=get_swarm_service_name_for_deployment(
                    deployment_hash=deployment.hash,
                    project_id=deployment.service.project_id,
                    service_id=deployment.service.id,
                ),
                mounts=mounts,
                endpoint_spec=endpoint_spec,
                env=envs,
                labels=get_resource_labels(
                    service.project_id,
                    deployment_hash=deployment.hash,
                    service=deployment.service.id,
                    status="active",
                ),
                networks=[
                    NetworkAttachmentConfig(
                        target=get_env_network_resource_name(
                            service.environment.id, service.project_id
                        ),
                        aliases=service.network_aliases,
                    ),
                    NetworkAttachmentConfig(
                        target="zane",
                        aliases=[deployment.network_alias],
                    ),
                ],
                update_config=UpdateConfig(
                    order="start-first",
                    parallelism=1,
                ),
                restart_policy=RestartPolicy(
                    condition="any",
                ),
                # this disables the default container healthcheck, since we control the healthcheck externally
                healthcheck=DockerHealthcheckType(test=["NONE"]),
                stop_grace_period=int(30e9),  # stop_grace_period is in nanoseconds
                log_driver="fluentd",
                log_driver_options={
                    "fluentd-address": settings.ZANE_FLUENTD_HOST,
                    "tag": json.dumps(
                        {
                            "service_id": deployment.service.id,
                            "deployment_id": deployment.hash,
                        }
                    ),
                    "mode": "non-blocking",
                    "fluentd-async": "true",
                    "fluentd-max-retries": "10",
                    "fluentd-sub-second-precision": "true",
                },
                resources=resources,
                configs=configs,
            )
            await deployment_log(
                deployment,
                f"Service created succesfully for the deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC} ✅",
            )

    @activity.defn
    async def run_deployment_healthcheck(
        self,
        deployment: DeploymentDetails,
    ) -> tuple[Deployment.DeploymentStatus, str]:
        docker_deployment = (
            await Deployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service.id
            )
            .select_related("service", "service__project", "service__healthcheck")
            .afirst()
        )

        if docker_deployment is None:
            raise ApplicationError(
                "Cannot check a status of a non existent deployment.",
                non_retryable=True,
            )

        swarm_service = self.docker_client.services.get(
            get_swarm_service_name_for_deployment(
                deployment_hash=docker_deployment.hash,
                project_id=docker_deployment.service.project.id,
                service_id=docker_deployment.service.id,
            )
        )

        start_time = monotonic()
        healthcheck = docker_deployment.service.healthcheck

        healthcheck_timeout = (
            healthcheck.timeout_seconds
            if healthcheck is not None
            else settings.DEFAULT_HEALTHCHECK_TIMEOUT
        )
        healthcheck_attempts = 0
        deployment_status, deployment_status_reason = (
            Deployment.DeploymentStatus.UNHEALTHY,
            "The service failed to meet the healthcheck requirements when starting the service.",
        )
        await deployment_log(
            deployment,
            f"Running healthchecks for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        while (monotonic() - start_time) < healthcheck_timeout:
            healthcheck_attempts += 1
            healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)

            await deployment_log(
                deployment,
                f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC}"
                f" | healthcheck_time_left={Colors.ORANGE}{format_seconds(healthcheck_time_left)}{Colors.ENDC} 💓",
            )

            task_list = swarm_service.tasks(
                filters={
                    "label": f"deployment_hash={docker_deployment.hash}",
                    "desired-state": "running",
                }
            )
            if len(task_list) > 0:
                most_recent_swarm_task = DockerSwarmTask.from_dict(
                    max(
                        task_list,
                        key=lambda task: task["Version"]["Index"],
                    )
                )

                # starting_status = DockerDeployment.DeploymentStatus.STARTING
                # # We set the status to restarting, because we get more than one task for this service when we restart it
                # if len(task_list) > 1:
                #     starting_status = DockerDeployment.DeploymentStatus.RESTARTING

                state_matrix = {
                    DockerSwarmTaskState.NEW: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PENDING: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ASSIGNED: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.ACCEPTED: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.READY: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.PREPARING: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.STARTING: Deployment.DeploymentStatus.STARTING,
                    DockerSwarmTaskState.RUNNING: Deployment.DeploymentStatus.HEALTHY,
                    DockerSwarmTaskState.COMPLETE: Deployment.DeploymentStatus.REMOVED,
                    DockerSwarmTaskState.FAILED: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.SHUTDOWN: Deployment.DeploymentStatus.REMOVED,
                    DockerSwarmTaskState.REJECTED: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.ORPHANED: Deployment.DeploymentStatus.UNHEALTHY,
                    DockerSwarmTaskState.REMOVE: Deployment.DeploymentStatus.REMOVED,
                }

                exited_without_error = 0
                deployment_status = state_matrix[most_recent_swarm_task.state]

                all_tasks = swarm_service.tasks(
                    filters={
                        "label": f"deployment_hash={docker_deployment.hash}",
                    }
                )
                if deployment_status == Deployment.DeploymentStatus.STARTING:
                    # We set the status to restarting, because we get more than one task for this service when we restart it
                    if len(all_tasks) > 1:
                        deployment_status = Deployment.DeploymentStatus.RESTARTING

                    docker_deployment.status = deployment_status
                    await docker_deployment.asave()

                deployment_status_reason = (
                    most_recent_swarm_task.Status.Err
                    if most_recent_swarm_task.Status.Err is not None
                    else most_recent_swarm_task.Status.Message
                )

                if most_recent_swarm_task.state == DockerSwarmTaskState.SHUTDOWN:
                    status_code = most_recent_swarm_task.Status.ContainerStatus.ExitCode  # type: ignore
                    if (
                        status_code is not None and status_code != exited_without_error
                    ) or most_recent_swarm_task.Status.Err is not None:
                        deployment_status = Deployment.DeploymentStatus.UNHEALTHY

                if (
                    most_recent_swarm_task.state == DockerSwarmTaskState.RUNNING
                    and most_recent_swarm_task.container_id is not None
                ):
                    if healthcheck is not None:
                        try:
                            print(
                                f"Running custom healthcheck {healthcheck.type=} - {healthcheck.value=}"
                            )
                            if healthcheck.type == HealthCheck.HealthCheckType.COMMAND:
                                container = self.docker_client.containers.get(
                                    most_recent_swarm_task.container_id
                                )
                                exit_code, output = container.exec_run(
                                    cmd=healthcheck.value,
                                    stdout=True,
                                    stderr=True,
                                    stdin=False,
                                )

                                if exit_code == 0:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.HEALTHY
                                    )
                                else:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.UNHEALTHY
                                    )
                                deployment_status_reason = output.decode("utf-8")
                            else:
                                full_url = f"http://{deployment.network_alias}:{healthcheck.associated_port}{healthcheck.value}"
                                response = requests.get(
                                    full_url,
                                    timeout=min(healthcheck_time_left, 5),
                                )
                                if status.is_success(response.status_code):
                                    deployment_status = (
                                        Deployment.DeploymentStatus.HEALTHY
                                    )
                                else:
                                    deployment_status = (
                                        Deployment.DeploymentStatus.UNHEALTHY
                                    )
                                deployment_status_reason = response.content.decode(
                                    "utf-8"
                                )
                        except (HTTPError, RequestException) as e:
                            deployment_status = Deployment.DeploymentStatus.UNHEALTHY
                            deployment_status_reason = str(e)

                healthcheck_time_left = healthcheck_timeout - (monotonic() - start_time)
                if (
                    deployment_status == Deployment.DeploymentStatus.HEALTHY
                    or healthcheck_time_left
                    <= settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL
                ):
                    status_color = (
                        Colors.GREEN
                        if deployment_status == Deployment.DeploymentStatus.HEALTHY
                        else Colors.RED
                    )
                    await deployment_log(
                        deployment,
                        f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                        f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                        f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC}",
                        error=status_color == Colors.RED,
                    )
                    await deployment_log(
                        deployment,
                        f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                        f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                        f"| finished with status {status_color}{deployment_status}{Colors.ENDC}",
                        error=status_color == Colors.RED,
                    )
                    return deployment_status, deployment_status_reason

            await deployment_log(
                deployment,
                f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC}",
                error=True,
            )
            await deployment_log(
                deployment,
                f"Healthcheck for deployment deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
                f"| FAILED, Retrying in {Colors.ORANGE}{format_seconds(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)}{Colors.ENDC} 🔄",
                error=True,
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)

        status_color = (
            Colors.GREEN
            if deployment_status == Deployment.DeploymentStatus.HEALTHY
            else Colors.RED
        )
        await deployment_log(
            deployment,
            f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
            f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
            f"| finished with result : {Colors.GREY}{deployment_status_reason}{Colors.ENDC} ✅",
        )
        await deployment_log(
            deployment,
            f"Healthcheck for deployment {Colors.ORANGE}{docker_deployment.hash}{Colors.ENDC}"
            f" | {Colors.BLUE}ATTEMPT #{healthcheck_attempts}{Colors.ENDC} "
            f"| finished with status {status_color}{deployment_status}{Colors.ENDC} ✅",
        )
        return deployment_status, deployment_status_reason

    @activity.defn
    async def expose_docker_deployment_to_http(
        self,
        deployment: DeploymentDetails,
    ):
        # add URL conf for deployment
        service = deployment.service
        if len(service.urls_with_associated_ports) > 0:
            ZaneProxyClient.insert_deployment_urls(deployment)

    @activity.defn
    async def expose_docker_service_to_http(
        self,
        deployment: DeploymentDetails,
    ):
        service = deployment.service
        if len(service.urls) > 0:
            await deployment_log(
                deployment,
                f"Configuring service URLs for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
            )
            previous_deployment: Deployment | None = await (
                Deployment.objects.filter(
                    Q(service_id=deployment.service.id)
                    & Q(queued_at__lt=deployment.queued_at_as_datetime)
                    & ~Q(hash=deployment.hash)
                )
                .order_by("-queued_at")
                .afirst()
            )

            for url in service.urls:
                ZaneProxyClient.upsert_service_url(
                    url=url,
                    current_deployment=deployment,
                    previous_deployment=previous_deployment,
                )

            await deployment_log(
                deployment,
                f"Service URLs for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC} configured successfully ✅",
            )

    @activity.defn
    async def scale_down_and_remove_docker_service_deployment(
        self, deployment: SimpleDeploymentDetails
    ):
        service_name = get_swarm_service_name_for_deployment(
            deployment_hash=deployment.hash,
            project_id=deployment.project_id,
            service_id=deployment.service_id,
        )
        try:
            swarm_service = self.docker_client.services.get(service_name)
        except docker.errors.NotFound:
            # Do nothing, The service has already been deleted
            pass
        else:
            swarm_service.scale(0)

            async def wait_for_service_to_be_down():
                print(f"waiting for service {swarm_service.name=} to be down...")
                task_list = swarm_service.tasks(filters={"desired-state": "running"})
                while len(task_list) > 0:
                    print(
                        f"service {swarm_service.name=} is not down yet, "
                        + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
                    )
                    await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
                    task_list = swarm_service.tasks(
                        filters={"desired-state": "running"}
                    )
                print(f"service {swarm_service.name=} is down, YAY !! 🎉")

            await wait_for_service_to_be_down()
            swarm_service.remove()
        finally:
            return service_name

    @activity.defn
    async def remove_old_docker_volumes(self, deployment: DeploymentDetails):
        service = deployment.service
        docker_volume_names = [
            get_volume_resource_name(volume.id)  # type: ignore
            for volume in service.docker_volumes
        ]

        docker_volume_list = self.docker_client.volumes.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service.project_id,
                        parent=service.id,
                    ).items()
                ]
            }
        )

        for volume in docker_volume_list:
            if volume.name not in docker_volume_names:
                volume.remove(force=True)

    @activity.defn
    async def remove_old_docker_configs(self, deployment: DeploymentDetails):
        service = deployment.service
        docker_config_names = [
            get_config_resource_name(config.id, config.version)  # type: ignore
            for config in service.configs
        ]

        docker_config_list = self.docker_client.configs.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(
                        service.project_id,
                        parent=service.id,
                    ).items()
                ]
            }
        )

        for config in docker_config_list:
            if config.name not in docker_config_names:
                config.remove()

    @activity.defn
    async def remove_old_urls(self, deployment: DeploymentDetails):
        ZaneProxyClient.cleanup_old_service_urls(deployment)

    @activity.defn
    async def unexpose_docker_service_from_http(
        self, service_details: ArchivedDockerServiceDetails | ArchivedGitServiceDetails
    ):
        for url in service_details.urls:
            ZaneProxyClient.remove_service_url(service_details.original_id, url)

        for deployment in service_details.deployments:
            for domain in deployment.urls:
                ZaneProxyClient.remove_deployment_url(deployment.hash, domain)

    @activity.defn
    async def unexpose_docker_deployment_from_http(self, deployment: DeploymentDetails):
        for url in deployment.urls:
            ZaneProxyClient.remove_deployment_url(deployment.hash, url.domain)

    @activity.defn
    async def remove_changed_urls_in_deployment(self, deployment: DeploymentDetails):
        new_urls = [
            URLDto.from_dict(change.new_value)
            for change in deployment.changes
            if change.type == DeploymentChange.ChangeType.ADD
            and change.field == DeploymentChange.ChangeField.URLS
        ]
        updated_url_changes = [
            change
            for change in deployment.changes
            if change.type == DeploymentChange.ChangeType.UPDATE
            and change.field == DeploymentChange.ChangeField.URLS
        ]
        for url in new_urls:
            ZaneProxyClient.remove_service_url(deployment.service.id, url)

        for url_change in updated_url_changes:
            old_url = URLDto.from_dict(url_change.old_value)
            new_url = URLDto.from_dict(url_change.new_value)

            # This is so that we don't delete the urls we just added
            # Sometimes the change can just be about `strip_prefix` and it might delete the old URL
            if (
                new_url.domain != old_url.domain
                or new_url.base_path != old_url.base_path
            ):
                ZaneProxyClient.remove_service_url(deployment.service.id, new_url)

        previous_deployment = await (
            Deployment.objects.filter(
                Q(service_id=deployment.service.id)
                & Q(is_current_production=True)
                & ~Q(hash=deployment.hash)
            )
            .select_related("service", "service__project")
            .order_by("-queued_at")
            .afirst()
        )
        # Reset old urls
        if (
            previous_deployment is not None
            and previous_deployment.service_snapshot is not None
        ):
            service = DockerServiceSnapshot.from_dict(
                previous_deployment.service_snapshot
            )
            for url in service.urls:
                ZaneProxyClient.upsert_service_url(
                    url=url,
                    current_deployment=previous_deployment,
                    previous_deployment=deployment,
                )

    @activity.defn
    async def create_deployment_stats_schedule(self, deployment: DeploymentDetails):
        try:
            docker_deployment = (
                await Deployment.objects.filter(hash=deployment.hash)
                .select_related("service")
                .afirst()
            )

            if docker_deployment is None:
                raise Deployment.DoesNotExist(
                    f"Docker deployment with hash='{deployment.hash}' does not exist."
                )
        except Deployment.DoesNotExist:
            raise ApplicationError(
                "Cannot create a stats schedule for a non existent deployment.",
                non_retryable=True,
            )
        else:
            details = SimpleDeploymentDetails(
                hash=deployment.hash,
                service_id=deployment.service.id,
                project_id=deployment.service.project_id,
            )
            try:
                await create_schedule(
                    workflow=GetDockerDeploymentStatsWorkflow.run,
                    args=details,
                    id=docker_deployment.metrics_schedule_id,
                    interval=timedelta(seconds=30),
                    task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
                )
            except ScheduleAlreadyRunningError:
                # the schedule already exists, ignore
                pass
            return docker_deployment.metrics_schedule_id

    @activity.defn
    async def create_deployment_healthcheck_schedule(
        self, deployment: DeploymentDetails
    ):
        try:
            docker_deployment = (
                await Deployment.objects.filter(hash=deployment.hash)
                .select_related("service", "service__healthcheck")
                .afirst()
            )

            if docker_deployment is None:
                raise Deployment.DoesNotExist(
                    f"Docker deployment with hash='{deployment.hash}' does not exist."
                )
        except Deployment.DoesNotExist:
            raise ApplicationError(
                "Cannot create a healthcheck schedule for a non existent deployment.",
                non_retryable=True,
            )
        else:
            healthcheck: Optional[HealthCheck] = docker_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=deployment.hash,
                    service_id=deployment.service.id,
                    project_id=deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                            associated_port=healthcheck.associated_port,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )

            interval_seconds = (
                healthcheck_details.healthcheck.interval_seconds
                if healthcheck_details.healthcheck is not None
                else settings.DEFAULT_HEALTHCHECK_INTERVAL
            )
            try:
                await create_schedule(
                    workflow=MonitorDockerDeploymentWorkflow.run,
                    args=healthcheck_details,
                    id=docker_deployment.monitor_schedule_id,
                    interval=timedelta(seconds=interval_seconds),
                    task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
                )
            except ScheduleAlreadyRunningError:
                # because the schedule already exists and is running, we can ignore it
                pass
            return docker_deployment.monitor_schedule_id
