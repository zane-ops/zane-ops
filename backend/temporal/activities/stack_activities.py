import asyncio
import shlex
import shutil
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
import os.path


with workflow.unsafe.imports_passed_through():
    from compose.models import ComposeStackDeployment
    from django.utils import timezone
    from ..helpers import deployment_log, get_docker_client, empty_folder
    from search.dtos import RuntimeLogSource
    from zane_api.utils import Colors, multiline_command
    from django.db.models import Case, F, Value, When


from ..constants import DOCKER_BINARY_PATH

from ..shared import ComposeStackDeploymentDetails, ComposeStackBuildDetails


class ComposeStackActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def prepare_deployment(self, deployment: ComposeStackDeploymentDetails):
        await deployment_log(
            deployment,
            f"Preparing compose stack deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )

        await ComposeStackDeployment.objects.filter(
            hash=deployment.hash,
            stack_id=deployment.stack_id,
            status=ComposeStackDeployment.DeploymentStatus.QUEUED,
        ).aupdate(
            status=ComposeStackDeployment.DeploymentStatus.DEPLOYING,
            started_at=timezone.now(),
        )

    @activity.defn
    async def create_temporary_directory_for_deploy(
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
        # 1. Empty the temp folder in case there is junk files in it
        print(f"Emptying folder {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC}...")
        await asyncio.to_thread(empty_folder, details.tmp_build_dir)
        print(
            f"Folder {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC} emptied succesfully ✅"
        )
        await deployment_log(
            deployment=details.deployment,
            message=f"Temporary build directory created at {Colors.ORANGE}{details.tmp_build_dir}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )

        stack_file_path = os.path.join(details.tmp_build_dir, "docker-stack.yml")
        # 2. create stack file
        await deployment_log(
            deployment=details.deployment,
            message=f"Creating docker-compose stack file at {Colors.ORANGE}{stack_file_path}{Colors.ENDC}...",
            source=RuntimeLogSource.BUILD,
        )

        with open(stack_file_path, "w") as file:
            file.write(details.deployment.computed_content)

            print("====== file contents: ======")
            print(file.read())
            print("====== END file contents ======")

        await deployment_log(
            deployment=details.deployment,
            message=f"Compose stack file created at {Colors.ORANGE}{stack_file_path}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )

        # 3. create config files
        # TODO

    @activity.defn
    async def deploy_stack_with_cli(self, details: ComposeStackBuildDetails):
        stack_file_path = os.path.join(details.tmp_build_dir, "docker-stack.yml")
        heartbeat_task = None
        cancel_event = asyncio.Event()
        try:

            async def send_heartbeat():
                """
                We want this activity to be cancellable,
                for activities to be cancellable, they need to send regular heartbeats:
                https://docs.temporal.io/develop/python/cancellation#cancel-activity
                """
                while True:
                    activity.heartbeat("Heartbeat from `deploy_stack_with_cli()`...")
                    await asyncio.sleep(0.1)

            heartbeat_task = asyncio.create_task(send_heartbeat())

            await deployment_log(
                deployment=details.deployment,
                message="Deploying the compose stack...",
                source=RuntimeLogSource.BUILD,
            )

            stack_name = f"zn-{details.deployment.stack_id}"
            cmd_args = [
                DOCKER_BINARY_PATH,
                "stack",
                "deploy",
                "--detach",
                "--compose-file",
                stack_file_path,
                "--with-registry-auth",
                stack_name,
            ]
            cmd_string = multiline_command(shlex.join(cmd_args))
            log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
            for index, msg in enumerate(log_message.splitlines()):
                await deployment_log(
                    deployment=details.deployment,
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
                    deployment=details.deployment,
                    message=info_lines,
                    source=RuntimeLogSource.BUILD,
                )
            if len(error_lines) > 0:
                await deployment_log(
                    deployment=details.deployment,
                    message=error_lines,
                    source=RuntimeLogSource.BUILD,
                    error=True,
                )
            if process.returncode != 0:
                await deployment_log(
                    deployment=details.deployment,
                    message=f"Error when deploying docker-compose stack {Colors.BLUE}{stack_name}{Colors.ENDC}",
                    source=RuntimeLogSource.BUILD,
                    error=True,
                )
                raise ApplicationError(
                    "Error when deploying docker-compose stack to registry",
                    non_retryable=True,
                )

        except asyncio.CancelledError as e:
            print(f"asyncio.CancelledError: {e=}")
            print(f"set {cancel_event=}")
            cancel_event.set()
            raise  # reraise to account as cancelled
        else:
            await deployment_log(
                deployment=details.deployment,
                message=f"Successfully deployed docker-compose stack {Colors.BLUE}{stack_name}{Colors.ENDC} ✅",
                source=RuntimeLogSource.BUILD,
            )
        finally:
            print(f"Cancelling {heartbeat_task=}")
            if heartbeat_task:
                heartbeat_task.cancel()

    @activity.defn
    async def expose_stack_services_to_http(
        self, deployment: ComposeStackDeploymentDetails
    ):
        pass  # TODO

    @activity.defn
    async def monitor_stack_health(self, deployment: ComposeStackDeploymentDetails):
        pass  # TODO

    @activity.defn
    async def finalize_deployment(self, deployment: ComposeStackDeploymentDetails):
        await deployment_log(
            deployment,
            f"Preparing compose stack deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )

        await ComposeStackDeployment.objects.filter(
            hash=deployment.hash,
            stack_id=deployment.stack_id,
        ).aupdate(
            status=ComposeStackDeployment.DeploymentStatus.SUCCEEDED,
            finished_at=Case(
                When(finished_at__isnull=True, then=Value(timezone.now())),
                default=F("finished_at"),
            ),
            started_at=Case(
                When(started_at__isnull=True, then=Value(timezone.now())),
                default=F("started_at"),
            ),
        )

        # TODO: finish this completely

    @activity.defn
    async def cleanup_temporary_directory_for_deploy(
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
