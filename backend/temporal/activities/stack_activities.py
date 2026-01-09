import asyncio
from datetime import timedelta
import shlex
import shutil
from time import monotonic
from typing import Any, Dict, List, cast
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
import os.path
from temporalio.client import ScheduleAlreadyRunningError
from temporalio.service import RPCError

with workflow.unsafe.imports_passed_through():
    from compose.models import ComposeStackDeployment, ComposeStack
    from compose.dtos import ComposeStackServiceStatus
    from django.utils import timezone
    from ..helpers import (
        deployment_log,
        get_docker_client,
        empty_folder,
        ZaneProxyClient,
    )
    from search.dtos import RuntimeLogSource
    from zane_api.utils import (
        Colors,
        multiline_command,
        DockerSwarmTask,
        format_duration,
    )
    from django.db.models import Case, F, Value, When
    from docker.models.services import Service as DockerService
    from django.conf import settings
    from ..schedules import MonitorComposeStackWorkflow
    from ..semaphore import AsyncSemaphore


from ..constants import DOCKER_BINARY_PATH, STACK_DEPLOY_SEMAPHORE_KEY
from ..client import TemporalClient

from ..shared import (
    ComposeStackDeploymentDetails,
    ComposeStackBuildDetails,
    ComposeStackMonitorPayload,
    ComposeStackArchiveDetails,
    ProxyURLRoute,
)


class ComposeStackActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def prepare_stack_deployment(self, deployment: ComposeStackDeploymentDetails):
        await deployment_log(
            deployment,
            f"Preparing compose stack deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )

        try:
            dpl = await ComposeStackDeployment.objects.aget(
                hash=deployment.hash,
                stack_id=deployment.stack.id,
                status=ComposeStackDeployment.DeploymentStatus.QUEUED,
            )
        except ComposeStackDeployment.DoesNotExist:
            raise ApplicationError(
                f"ComposeStack deployment with hash {deployment.hash} does not exist for this stack",
                non_retryable=True,
            )
        else:
            dpl.status = ComposeStackDeployment.DeploymentStatus.DEPLOYING
            dpl.started_at = timezone.now()

            await dpl.asave(update_fields=["status", "started_at", "updated_at"])

    @activity.defn
    async def create_temporary_directory_for_stack_deployment(
        self,
        deployment: ComposeStackDeploymentDetails,
    ) -> str:
        await deployment_log(
            deployment=deployment,
            message="Creating temporary directory for building the app...",
            source=RuntimeLogSource.BUILD,
        )
        temp_dir = tempfile.mkdtemp()

        return temp_dir

    @activity.defn
    async def create_files_in_docker_stack_folder(
        self, details: ComposeStackBuildDetails
    ):
        deployment = details.deployment
        stack = details.deployment.stack
        # 1. Empty the temp folder in case there is junk files in it
        print(f"Emptying folder {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC}...")
        await asyncio.to_thread(empty_folder, details.tmp_build_dir)
        print(
            f"Folder {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC} emptied succesfully ✅"
        )
        await deployment_log(
            deployment=deployment,
            message=f"Temporary build directory created at {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )

        stack_file_path = os.path.join(details.tmp_build_dir, "docker-stack.yml")
        # 2. create stack file
        await deployment_log(
            deployment=deployment,
            message=f"Creating docker-compose stack file at {Colors.ORANGE}{stack_file_path}{Colors.ENDC}...",
            source=RuntimeLogSource.BUILD,
        )

        with open(stack_file_path, "w") as file:
            file.write(stack.computed_content)

            print("====== file contents: ======")
            print(stack.computed_content)
            print("====== END file contents ======")

        await deployment_log(
            deployment=deployment,
            message=f"Compose stack file created at {Colors.ORANGE}{stack_file_path}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )

        # 3. create config files
        for name, contents in stack.configs.items():
            config_file_path = os.path.join(
                details.tmp_build_dir, f"{stack.hash_prefix}_{name}.conf"
            )
            with open(config_file_path, "w") as file:
                file.write(contents)

    @activity.defn
    async def deploy_stack_with_cli(self, details: ComposeStackBuildDetails):
        stack_file_path = os.path.join(details.tmp_build_dir, "docker-stack.yml")

        deployment = details.deployment

        await deployment_log(
            deployment=deployment,
            message="Deploying the compose stack...",
            source=RuntimeLogSource.BUILD,
        )

        cmd_args = [
            DOCKER_BINARY_PATH,
            "stack",
            "deploy",
            "--detach",
            "--compose-file",
            stack_file_path,
            "--with-registry-auth",
            deployment.stack.name,
        ]
        cmd_string = multiline_command(shlex.join(cmd_args))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        for index, msg in enumerate(log_message.splitlines()):
            await deployment_log(
                deployment=deployment,
                message=f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg,
                source=RuntimeLogSource.BUILD,
            )

        process = await asyncio.create_subprocess_shell(
            shlex.join(cmd_args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        info_lines = stdout.decode().splitlines()
        error_lines = stderr.decode().splitlines()
        if len(info_lines) > 0:
            await deployment_log(
                deployment=deployment,
                message=info_lines,
                source=RuntimeLogSource.BUILD,
            )
        if len(error_lines) > 0:
            await deployment_log(
                deployment=deployment,
                message=error_lines,
                source=RuntimeLogSource.BUILD,
                error=True,
            )
        if process.returncode != 0:
            await deployment_log(
                deployment=deployment,
                message=f"Error when deploying docker-compose stack {Colors.BLUE}{deployment.stack.name}{Colors.ENDC}",
                source=RuntimeLogSource.BUILD,
                error=True,
            )
            raise ApplicationError(
                "Error when deploying docker-compose stack to registry",
                non_retryable=True,
            )

        await deployment_log(
            deployment=deployment,
            message=f"Successfully deployed docker-compose stack {Colors.BLUE}{deployment.stack.name}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )

    @activity.defn
    async def expose_stack_services_to_http(
        self, deployment: ComposeStackDeploymentDetails
    ):
        stack = deployment.stack
        for service_name, service_urls in stack.urls.items():
            for url in service_urls:
                ZaneProxyClient.upsert_compose_stack_service_url(
                    stack_id=deployment.stack.id,
                    service_name=service_name,
                    stack_hash_prefix=stack.hash_prefix,
                    url=url,
                )

    async def _get_service_status(
        self,
        service: DockerService,
        stack_name: str,
        stack_hash_prefix: str,
    ) -> Dict[str, Any]:
        service_mode = service.attrs["Spec"]["Mode"]
        # Mode is a dict in the format:
        # {
        #   "Mode": {
        #     "Replicated": {
        #       "Replicas": 0
        #     },
        #     "Global": {},
        #     "ReplicatedJob": {
        #       "MaxConcurrent": 1,
        #       "TotalCompletions": 0
        #     },
        #     "GlobalJob": {}
        #   }
        # }

        service_status = service.attrs["ServiceStatus"]
        # ServiceStatus is a dict in the format:
        # {
        #   "RunningTasks": 1,
        #   "DesiredTasks": 1,
        #   "CompletedTasks": 0
        # }

        # Determine mode type
        if "Global" in service_mode:
            mode_type = "global"
        elif "ReplicatedJob" in service_mode:
            mode_type = "replicated-job"
        elif "GlobalJob" in service_mode:
            mode_type = "global-job"
        else:
            # default is replicated
            mode_type = "replicated"

        # Get counts from ServiceStatus
        running_replicas = service_status["RunningTasks"]
        desired_replicas = service_status["DesiredTasks"]
        completed_replicas = service_status.get("CompletedTasks", 0)

        # Get all tasks for the tasks list
        tasks = [DockerSwarmTask.from_dict(task) for task in service.tasks()]

        # Determine status based on mode
        is_job = mode_type in ["replicated-job", "global-job"]

        if is_job:
            # For jobs, healthy means completed >= desired
            status = (
                ComposeStackServiceStatus.HEALTHY
                if completed_replicas >= desired_replicas
                else ComposeStackServiceStatus.STARTING
            )
        else:
            # For regular services, healthy means running >= desired
            status = (
                ComposeStackServiceStatus.HEALTHY
                if running_replicas >= desired_replicas
                else ComposeStackServiceStatus.STARTING
            )

        return {
            "name": cast(str, service.name)
            .removeprefix(f"{stack_name}_")
            .removeprefix(f"{stack_hash_prefix}_"),
            "mode": mode_type,
            "status": status,
            "desired_replicas": desired_replicas,
            "running_replicas": running_replicas,
            "updated_at": timezone.now().isoformat(),
            "tasks": [
                {
                    "status": task.state.value,
                    "message": task.Status.Message,
                    "exit_code": task.Status.ContainerStatus.ExitCode
                    if task.Status.ContainerStatus
                    else None,
                }
                for task in tasks
            ],
        }

    @activity.defn
    async def check_stack_health(self, deployment: ComposeStackDeploymentDetails):
        mononotic_time = timedelta(minutes=5)

        services: List[DockerService] = self.docker_client.services.list(
            filters={"label": [f"com.docker.stack.namespace={deployment.stack.name}"]},
            status=True,
        )
        start_time = monotonic()

        status_message = f"0/{len(services)} of services healthy"
        total_healthy = 0
        await deployment_log(
            deployment,
            f"Checking health for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )
        check_attempts = 0
        while monotonic() - start_time < mononotic_time.total_seconds():
            activity.heartbeat("Heartbeat from `check_stack_health()`...")

            check_attempts += 1
            time_left = mononotic_time.total_seconds() - (monotonic() - start_time)

            await deployment_log(
                deployment,
                f"Health check for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{check_attempts}{Colors.ENDC}"
                f" | time_left={Colors.ORANGE}{format_duration(time_left)}{Colors.ENDC} 💓",
            )

            statuses = await asyncio.gather(
                *[
                    self._get_service_status(
                        service=service,
                        stack_name=deployment.stack.name,
                        stack_hash_prefix=deployment.stack.hash_prefix,
                    )
                    for service in services
                ]
            )

            service_statuses = {}
            for status in statuses:
                name = status.pop("name")
                service_statuses[name] = status

            await ComposeStack.objects.filter(id=deployment.stack.id).aupdate(
                service_statuses=service_statuses,
                updated_at=timezone.now(),
            )

            total_healthy = len(
                [
                    status["status"] == ComposeStackServiceStatus.HEALTHY
                    or status["status"] == ComposeStackServiceStatus.COMPLETE
                    for status in statuses
                ]
            )
            status_message = f"{total_healthy}/{len(services)} of services healthy"
            all_healthy = total_healthy == len(services)

            status_color = Colors.GREEN if all_healthy else Colors.RED

            await deployment_log(
                deployment,
                f"Health check for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{check_attempts}{Colors.ENDC} "
                f"| result: {status_color}{status_message}{Colors.ENDC}",
            )

            if all_healthy:
                break
            await deployment_log(
                deployment,
                f"Health check for deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}"
                f" | {Colors.BLUE}ATTEMPT #{check_attempts}{Colors.ENDC} | {Colors.GREY}some services still starting or unhealthy{Colors.ENDC}"
                f"| Retrying in {Colors.ORANGE}{format_duration(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)}{Colors.ENDC} 🔄",
                error=True,
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)

        return ComposeStackDeployment.DeploymentStatus.FINISHED, status_message

    @activity.defn
    async def create_stack_healthcheck_schedule(
        self, deployment: ComposeStackDeploymentDetails
    ):
        try:
            await TemporalClient.acreate_schedule(
                workflow=MonitorComposeStackWorkflow.run,
                args=deployment.stack,
                id=deployment.stack.monitor_schedule_id,
                interval=timedelta(seconds=30),
                task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
            )
        except ScheduleAlreadyRunningError:
            # because the schedule already exists and is running, we can ignore it
            pass

    @activity.defn
    async def delete_stack_healthcheck_schedule(
        self, details: ComposeStackArchiveDetails
    ):
        try:
            await TemporalClient.adelete_schedule(
                id=details.stack.monitor_schedule_id,
            )
        except RPCError:
            # the schedule might have already been deleted
            pass

    @activity.defn
    async def finalize_deployment(self, result: ComposeStackMonitorPayload):
        deployment = result.deployment

        status_color = (
            Colors.GREEN
            if result.status == ComposeStackDeployment.DeploymentStatus.FINISHED
            else Colors.RED
        )

        await deployment_log(
            deployment,
            f"Compose stack deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC} finished with status {status_color}{result.status}{Colors.ENDC}",
        )

        await deployment_log(
            deployment,
            f"Compose stack deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC} finished with reason {Colors.GREY}{result.status_message}{Colors.ENDC}",
        )

        await ComposeStackDeployment.objects.filter(
            hash=deployment.hash,
            stack_id=deployment.stack.id,
        ).aupdate(
            status=result.status,
            status_reason=result.status_message,
            finished_at=Case(
                When(finished_at__isnull=True, then=Value(timezone.now())),
                default=F("finished_at"),
            ),
            started_at=Case(
                When(started_at__isnull=True, then=Value(timezone.now())),
                default=F("started_at"),
            ),
        )

    @activity.defn
    async def cleanup_temporary_directory_for_stack_deployment(
        self, details: ComposeStackBuildDetails
    ):
        await deployment_log(
            deployment=details.deployment,
            message=f"Cleaning up temporary directory at {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC}...",
            source=RuntimeLogSource.BUILD,
        )
        shutil.rmtree(details.tmp_build_dir, ignore_errors=True)
        await deployment_log(
            deployment=details.deployment,
            message="Temporary directory deleted ✅",
            source=RuntimeLogSource.BUILD,
        )

    @activity.defn
    async def unexpose_stack_services_from_http(
        self, details: ComposeStackArchiveDetails
    ) -> List[ProxyURLRoute]:
        print(
            f"Deleting URLs for the stack {Colors.BLUE}{details.stack.slug}{Colors.ENDC} (id: {Colors.ORANGE}{details.stack.id}{Colors.ENDC})..."
        )
        urls_deleted = await ZaneProxyClient.cleanup_stack_service_urls(
            details.stack.id
        )
        print(
            f"Deleted {len(urls_deleted)} URLs for the stack {Colors.BLUE}{details.stack.slug}{Colors.ENDC} (id: {Colors.ORANGE}{details.stack.id}{Colors.ENDC}) ✅"
        )
        return urls_deleted

    @activity.defn
    async def get_services_in_stack(
        self, details: ComposeStackArchiveDetails
    ) -> List[str]:
        stack = details.stack
        services: List[DockerService] = self.docker_client.services.list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]},
        )

        return [service.name for service in services]

    @activity.defn
    async def wait_for_stack_service_containers_to_be_deleted(self, service: str):
        print(f"waiting for containers for service {service=} to be removed...")
        container_list = self.docker_client.containers.list(filters={"name": service})
        while len(container_list) > 0:
            print(
                f"service {service=} is not removed yet, "
                + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
            container_list = self.docker_client.containers.list(
                filters={"name": service}
            )
            continue
        print(f"service {service=} is removed, YAY !! 🎉")

    @activity.defn
    async def delete_stack_configs(
        self, details: ComposeStackArchiveDetails
    ) -> List[str]:
        stack = details.stack
        configs = self.docker_client.configs.list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]},
        )

        for config in configs:
            config.remove()
        print(f"Deleted {len(configs)} config(s), YAY !! 🎉")
        return [config.name for config in configs]

    @activity.defn
    async def delete_stack_volumes(
        self, details: ComposeStackArchiveDetails
    ) -> List[str]:
        stack = details.stack
        volumes = self.docker_client.volumes.list(
            filters={"label": [f"com.docker.stack.namespace={stack.name}"]},
        )

        for volume in volumes:
            volume.remove(force=True)
        print(f"Deleted {len(volumes)} volume(s), YAY !! 🎉")
        return [volume.name for volume in volumes]

    @activity.defn
    async def remove_stack_with_cli(self, details: ComposeStackArchiveDetails):
        print("Removing the compose stack...")
        stack = details.stack

        cmd_args = [
            DOCKER_BINARY_PATH,
            "stack",
            "rm",
            stack.name,
        ]
        cmd_string = multiline_command(shlex.join(cmd_args))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        for index, msg in enumerate(log_message.splitlines()):
            print(f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg)

        process = await asyncio.create_subprocess_shell(
            shlex.join(cmd_args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        info_lines = stdout.decode().splitlines()
        error_lines = stderr.decode().splitlines()
        if len(info_lines) > 0:
            print("\n".join(info_lines))
        if len(error_lines) > 0:
            print("\n".join(error_lines))
        if process.returncode != 0:
            print(
                f"{Colors.RED}Error when deploying docker-compose stack {Colors.BLUE}{stack.name}{Colors.ENDC}"
            )
            # do not raise error because the stack might not exist anymore
        else:
            print(
                f"Successfully removed docker-compose stack {Colors.BLUE}{stack.name}{Colors.ENDC} ✅"
            )

    @activity.defn
    async def lock_stack_deploy_semaphore(self, stack_id: str):
        print(
            f"Locking deploy semaphore for stack {Colors.ORANGE}{stack_id}{Colors.ENDC}..."
        )
        if not settings.TESTING:
            # semaphores block test execution and hang forever,
            # so they are ignored in tests
            semaphore = AsyncSemaphore(
                key=f"{STACK_DEPLOY_SEMAPHORE_KEY}_{stack_id}",
                limit=1,
                semaphore_timeout=timedelta(
                    minutes=25
                ),  # this is to prevent the system cleanup from blocking for too long
            )
            await semaphore.acquire_all()
        print(f"Semaphore for stack {Colors.ORANGE}{stack_id}{Colors.ENDC} locked ✅")

    @activity.defn
    async def reset_stack_deploy_semaphore(self, stack_id: str):
        print(
            f"Resetting deploy semaphore for stack {Colors.ORANGE}{stack_id}{Colors.ENDC}..."
        )
        if not settings.TESTING:
            # semaphores block test execution and hang forever,
            # so they are ignored in tests
            semaphore = AsyncSemaphore(
                key=f"{STACK_DEPLOY_SEMAPHORE_KEY}_{stack_id}",
                limit=1,
                semaphore_timeout=timedelta(
                    minutes=25
                ),  # this is to prevent the system cleanup from blocking for too long
            )
            await semaphore.reset()
        print(f"Semaphore for stack {Colors.ORANGE}{stack_id}{Colors.ENDC} reset ✅")
