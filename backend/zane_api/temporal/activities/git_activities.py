import asyncio
import itertools
from typing import Optional, Set, cast
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
import os.path
from typing import Any
import re
from asgiref.sync import async_to_sync

with workflow.unsafe.imports_passed_through():
    import docker.errors
    from ...models import Deployment, Service
    from docker.utils.json_stream import json_stream
    import shutil
    import glob
    from ...git_client import GitClient, GitCloneFailedError, GitCheckoutFailedError
    from ..helpers import (
        deployment_log,
        get_docker_client,
        get_resource_labels,
        replace_placeholders,
        get_env_network_resource_name,
        generate_caddyfile_for_static_website,
    )
    from search.dtos import RuntimeLogSource
    from ...utils import Colors
    from django.utils import timezone
    from threading import Event


from ..shared import (
    DockerfileBuilderDetails,
    DockerfileBuilderGeneratedResult,
    GitBuildDetails,
    DeploymentDetails,
    GitCommitDetails,
    GitDeploymentDetailsWithCommitMessage,
    StaticBuilderDetails,
    StaticBuilderGeneratedResult,
    NixpacksBuilderGeneratedResult,
    GitCloneDetails,
    NixpacksBuilderDetails,
)
from ..constants import DOCKERFILE_STATIC, REPOSITORY_CLONE_LOCATION


class GitActivities:
    def __init__(self):
        self.docker_client = get_docker_client()
        self.git_client = GitClient()

    @activity.defn
    async def create_temporary_directory_for_build(
        self, deployment: DeploymentDetails
    ) -> str:
        await deployment_log(
            deployment=deployment,
            message="Creating temporary directory for building the app...",
            source=RuntimeLogSource.BUILD,
        )
        temp_dir = tempfile.mkdtemp()
        await deployment_log(
            deployment=deployment,
            message=f"Temporary build directory created at {Colors.ORANGE}{temp_dir}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )
        return temp_dir

    @activity.defn
    async def cleanup_temporary_directory_for_build(self, details: GitCloneDetails):
        await deployment_log(
            deployment=details.deployment,
            message=f"Cleaning up temporary build directory at {Colors.ORANGE}{details.location}{Colors.ENDC}...",
            source=RuntimeLogSource.BUILD,
        )
        shutil.rmtree(details.location, ignore_errors=True)
        await deployment_log(
            deployment=details.deployment,
            message="Temporary Build directory deleted ✅",
            source=RuntimeLogSource.BUILD,
        )

    @activity.defn
    async def clone_repository_and_checkout_to_commit(
        self, details: GitCloneDetails
    ) -> Optional[GitCommitDetails]:
        heartbeat_task = None
        cancel_event = Event()
        build_location = os.path.join(details.location, REPOSITORY_CLONE_LOCATION)
        try:

            async def send_heartbeat():
                """
                We want this activity to be cancellable,
                for activities to be cancellable, they need to send regular heartbeats:
                https://docs.temporal.io/develop/python/cancellation#cancel-activity
                """
                while True:
                    print(
                        "Sending heartbeat from `clone_repository_and_checkout_to_commit()`"
                    )
                    activity.heartbeat(
                        "Heartbeat from `clone_repository_and_checkout_to_commit()`..."
                    )
                    await asyncio.sleep(0.1)

            task_set: Set[asyncio.Task] = set()
            heartbeat_task = asyncio.create_task(send_heartbeat())
            task_set.add(heartbeat_task)

            service = details.deployment.service
            deployment = details.deployment

            try:
                git_deployment = (
                    await Deployment.objects.filter(
                        hash=deployment.hash, service_id=deployment.service.id
                    )
                    .select_related("service")
                    .aget()
                )
            except Deployment.DoesNotExist:
                raise ApplicationError(
                    "Cannot update a non existent deployment.",
                    non_retryable=True,
                )

            git_deployment.status = Deployment.DeploymentStatus.BUILDING
            await git_deployment.asave()

            await deployment_log(
                deployment=details.deployment,
                message=f"Cloning repository {Colors.ORANGE}{service.repository_url}{Colors.ENDC} to {Colors.ORANGE}{build_location}{Colors.ENDC}...",
                source=RuntimeLogSource.BUILD,
            )
            try:

                def message_handler(msg: str):
                    async_to_sync(deployment_log)(
                        deployment=details.deployment,
                        message=msg,
                        source=RuntimeLogSource.BUILD,
                    )
                    if cancel_event.is_set():
                        print(
                            f"{Colors.RED}Received cancel_event: {cancel_event} {Colors.ENDC}"
                        )
                        # Optionally raise an exception to abort the clone
                        raise GitCloneFailedError("Clone operation cancelled")

                clone_task = asyncio.create_task(
                    asyncio.to_thread(
                        self.git_client.clone_repository,
                        url=service.repository_url,  # type: ignore - this is defined in the case of git services
                        dest_path=build_location,
                        branch=service.branch_name,  # type: ignore - this is defined in the case of git services
                        clone_progress_handler=message_handler,
                    )
                )
                task_set.add(clone_task)
                done_first, _ = await asyncio.wait(
                    task_set, return_when=asyncio.FIRST_COMPLETED
                )
                if clone_task in done_first:
                    repo = clone_task.result()
                    print("Clone task finished first ?")
                    # Cancel heartbeat if clone finished first
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        heartbeat_task = None
                else:
                    clone_task.cancel()
                    await clone_task
            except GitCloneFailedError as e:
                await deployment_log(
                    deployment=details.deployment,
                    message=f"Failed to clone the repository to {Colors.ORANGE}{build_location}{Colors.ENDC} ❌: {Colors.GREY}{e}{Colors.ENDC}",
                    source=RuntimeLogSource.BUILD,
                    error=True,
                )
            else:
                await deployment_log(
                    deployment=details.deployment,
                    message="Repository cloned succesfully ✅",
                    source=RuntimeLogSource.BUILD,
                )
                await deployment_log(
                    deployment=details.deployment,
                    message=f"Checking out the repository at commit {Colors.ORANGE}{(deployment.commit_sha or 'HEAD')[:7]}{Colors.ENDC}...",
                    source=RuntimeLogSource.BUILD,
                )
                try:
                    commit = self.git_client.checkout_repository(repo, deployment.commit_sha)  # type: ignore - this is defined in the case of git services
                except GitCheckoutFailedError as e:
                    await deployment_log(
                        deployment=details.deployment,
                        message=f"Failed to checkout the repository at commit {Colors.ORANGE}{(deployment.commit_sha or 'HEAD')[:7]}{Colors.ENDC} ❌: {Colors.GREY}{e}{Colors.ENDC}",
                        source=RuntimeLogSource.BUILD,
                        error=True,
                    )
                else:
                    await deployment_log(
                        deployment=details.deployment,
                        message="Repository checked out succesfully ✅",
                        source=RuntimeLogSource.BUILD,
                    )
                    commit_details = GitCommitDetails(
                        author_name=commit.author.name,  # type: ignore - this is normally always defined
                        commit_message=(
                            commit.message.strip()
                            if isinstance(commit.message, str)
                            else commit.message.decode("utf-8").strip()
                        ),
                    )
                    return commit_details
        except asyncio.CancelledError as e:
            print(f"asyncio.CancelledError: {e=}")
            print(f"set {cancel_event=}")
            cancel_event.set()
            raise  # reraise to account as cancelled
        finally:
            print(f"Cancelling {heartbeat_task=}")
            if heartbeat_task:
                heartbeat_task.cancel()

    @activity.defn
    async def update_deployment_commit_message_and_author(
        self, details: GitDeploymentDetailsWithCommitMessage
    ):
        deployment = details.deployment
        git_deployment = (
            await Deployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service.id
            )
            .select_related("service")
            .afirst()
        )

        if git_deployment is None:
            raise ApplicationError(
                "Cannot update a non existent deployment.",
                non_retryable=True,
            )

        git_deployment.commit_message = details.commit.commit_message
        git_deployment.commit_author_name = details.commit.author_name
        await git_deployment.asave()

    @activity.defn
    async def build_service_with_dockerfile(
        self, details: GitBuildDetails
    ) -> Optional[str]:
        cancel_event = Event()
        heartbeat_task = None

        async def send_heartbeat():
            """
            We want this activity to be cancellable,
            for activities to be cancellable, they need to send regular heartbeats:
            https://docs.temporal.io/develop/python/cancellation#cancel-activity
            """
            while True:
                print("Sending heartbeat from `build_service_with_dockerfile()`")
                activity.heartbeat(
                    "Heartbeat from `build_service_with_dockerfile()`..."
                )
                await asyncio.sleep(0.1)

        try:
            task_set: Set[asyncio.Task] = set()
            heartbeat_task = asyncio.create_task(send_heartbeat())
            task_set.add(heartbeat_task)
            deployment = details.deployment
            service = deployment.service

            current_deployment = Deployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service.id
            ).select_related("service")

            git_deployment = await current_deployment.afirst()
            if git_deployment is None:
                raise ApplicationError(
                    "Cannot update a non existent deployment.",
                    non_retryable=True,
                )

            await current_deployment.aupdate(build_started_at=timezone.now())

            base_image = service.id.replace(Service.ID_PREFIX, "").lower()
            try:

                parent_environment_variables = {
                    env.key: env.value for env in service.environment.variables
                }

                build_envs = {**parent_environment_variables}
                build_envs.update(
                    {
                        env.key: replace_placeholders(
                            env.value, parent_environment_variables, "env"
                        )
                        for env in service.env_variables
                    }
                )
                build_envs.update(
                    {
                        env.key: replace_placeholders(
                            env.value,
                            {
                                "slot": deployment.slot,
                                "hash": deployment.hash,
                            },
                            "deployment",
                        )
                        for env in service.system_env_variables
                    }
                )

                build_network = get_env_network_resource_name(
                    service.environment.id, service.project_id
                )

                # Construct each line of the build command as a separate string
                cmd_lines = []

                cmd_lines.append("docker build \\")
                cmd_lines.append(f"-t {deployment.image_tag} \\")
                cmd_lines.append(f"-f {details.dockerfile_path} \\")

                # Append build arguments, each on its own line
                for key, value in build_envs.items():
                    cmd_lines.append(f"--build-arg {key}={value} \\")

                if details.build_stage_target:
                    cmd_lines.append(f"--target {details.build_stage_target} \\")
                if deployment.ignore_build_cache:
                    cmd_lines.append("--no-cache \\")

                # Append label arguments
                resource_labels = get_resource_labels(
                    service.project_id, parent=service.id
                )
                for k, v in resource_labels.items():
                    cmd_lines.append(f"--label {k}={v} \\")

                cmd_lines.append(f"--network={build_network} \\")
                cmd_lines.append(
                    f"--cpu-shares=512 \\ {Colors.GREY}# limit cpu usage to 50%{Colors.ENDC}"
                )
                # Finally, add the build context directory
                cmd_lines.append(details.build_context_dir)

                # Log each line separately using deployment_log
                for index, line in enumerate(cmd_lines):
                    await deployment_log(
                        deployment=deployment,
                        message=(
                            f"\t{Colors.YELLOW}{line}{Colors.ENDC}"
                            if index > 0
                            else f"Running {Colors.YELLOW}{line}{Colors.ENDC}"
                        ),
                        source=RuntimeLogSource.BUILD,
                    )
                await deployment_log(
                    deployment=deployment,
                    message="===================== RUNNING DOCKER BUILD ===========================",
                    source=RuntimeLogSource.BUILD,
                )

                def build_image():
                    build_output = self.docker_client.api.build(
                        path=details.build_context_dir,
                        dockerfile=details.dockerfile_path,
                        tag=deployment.image_tag,
                        buildargs=build_envs,
                        target=details.build_stage_target,
                        rm=True,
                        labels=get_resource_labels(
                            service.project_id, parent=service.id
                        ),
                        nocache=deployment.ignore_build_cache,
                        network_mode=build_network,
                        container_limits={
                            "cpushares": 512,  # Relative CPU weight (1024 = full CPU, 512 = 50%)
                        },
                    )
                    image_id = None
                    _, build_output = itertools.tee(json_stream(build_output))
                    loops = 0
                    for chunk in build_output:
                        loops += 1
                        log: dict[str, Any] = chunk  # type: ignore
                        if "error" in log:
                            log_lines = [
                                f"{Colors.RED}{line}{Colors.ENDC}"
                                for line in cast(
                                    str, log["error"].rstrip()
                                ).splitlines()
                            ]
                            async_to_sync(deployment_log)(
                                deployment=details.deployment,
                                message=log_lines,
                                source=RuntimeLogSource.BUILD,
                                error=True,
                            )
                        if "stream" in log:
                            log_lines = [
                                f"{Colors.BLUE}{line}{Colors.ENDC}"
                                for line in cast(
                                    str, log["stream"].rstrip()
                                ).splitlines()
                            ]
                            async_to_sync(deployment_log)(
                                deployment=details.deployment,
                                message=log_lines,
                                source=RuntimeLogSource.BUILD,
                            )
                            match = re.search(
                                r"(^Successfully built |sha256:)([0-9a-f]+)$",
                                log["stream"],
                            )
                            if match:
                                image_id = match.group(2)

                        if cancel_event.is_set():
                            print(
                                f"{Colors.RED}Received cancel_event: {cancel_event} {Colors.ENDC}"
                            )
                            return None
                    return image_id

                image_id = None
                build_image_task = asyncio.create_task(asyncio.to_thread(build_image))

                task_set.add(build_image_task)
                done_first, _ = await asyncio.wait(
                    task_set, return_when=asyncio.FIRST_COMPLETED
                )
                if build_image_task in done_first:
                    image_id = build_image_task.result()
                    print("`build_image_task()` finished first")
                    # Cancel heartbeat if clone finished first
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        heartbeat_task = None
                else:
                    print("cancelling `build_image_task()`")
                    build_image_task.cancel()
                    await build_image_task
            except TypeError as e:
                await deployment_log(
                    deployment=details.deployment,
                    message=f"Failed building the service ❌: {Colors.GREY}{e}{Colors.ENDC}",
                    source=RuntimeLogSource.BUILD,
                    error=True,
                )
            else:
                if not image_id:
                    await deployment_log(
                        deployment=details.deployment,
                        message="Failed building the service ❌",
                        source=RuntimeLogSource.BUILD,
                        error=True,
                    )
                    return None

                image = self.docker_client.images.get(image_id)
                image.tag(base_image, "latest", force=True)

                await deployment_log(
                    deployment=details.deployment,
                    message=f"Service build complete. Tagged as {Colors.ORANGE}{deployment.image_tag} ({image_id}){Colors.ENDC} ✅",
                    source=RuntimeLogSource.BUILD,
                )
                return image_id
            finally:
                await deployment_log(
                    deployment=deployment,
                    message="======================== DOCKER BUILD FINISHED  ========================",
                    source=RuntimeLogSource.BUILD,
                )
                await current_deployment.aupdate(build_finished_at=timezone.now())
        except asyncio.CancelledError:
            cancel_event.set()
            if heartbeat_task:
                heartbeat_task.cancel()

            await deployment_log(
                deployment=details.deployment,
                message=f"{Colors.YELLOW}docker build{Colors.ENDC} has been cancelled, but it might still continue in the background",
                source=RuntimeLogSource.BUILD,
            )
            raise

    @activity.defn
    async def cleanup_built_image(self, image_tag: str):
        try:
            image = self.docker_client.images.get(image_tag)
        except docker.errors.NotFound:
            pass
        else:
            image.remove(force=True)

    @activity.defn
    async def generate_default_files_for_dockerfile_builder(
        self, details: DockerfileBuilderDetails
    ) -> DockerfileBuilderGeneratedResult:
        build_location = os.path.join(details.temp_build_dir, REPOSITORY_CLONE_LOCATION)
        build_context_dir = os.path.normpath(
            os.path.join(build_location, details.builder_options.build_context_dir)
        )
        dockerfile_path = os.path.normpath(
            os.path.join(build_location, details.builder_options.dockerfile_path)
        )
        return DockerfileBuilderGeneratedResult(
            build_context_dir=build_context_dir, dockerfile_path=dockerfile_path
        )

    @activity.defn
    async def generate_default_files_for_static_builder(
        self, details: StaticBuilderDetails
    ) -> StaticBuilderGeneratedResult:
        await deployment_log(
            deployment=details.deployment,
            message=f"Generating default {Colors.ORANGE}Caddyfile{Colors.ENDC} and {Colors.ORANGE}Dockerfile{Colors.ENDC} for static builder...",
            source=RuntimeLogSource.BUILD,
        )
        caddyfile_contents = generate_caddyfile_for_static_website(
            details.builder_options
        )
        publish_directory = os.path.normpath(
            os.path.join(
                REPOSITORY_CLONE_LOCATION, details.builder_options.publish_directory
            )
        )
        dockerfile_contents = replace_placeholders(
            DOCKERFILE_STATIC,
            {"dir": f"./{publish_directory}/"},
            placeholder="publish",
        )

        # Use the custom Caddyfile at this location instead
        custom_caddyfile_path = os.path.normpath(
            os.path.join(details.temp_build_dir, publish_directory, "Caddyfile")
        )
        use_custom_caddyfile = os.path.isfile(custom_caddyfile_path)
        if use_custom_caddyfile:
            with open(custom_caddyfile_path, "r") as file:
                caddyfile_contents = file.read()

            await deployment_log(
                deployment=details.deployment,
                message=f"Using custom {Colors.ORANGE}Caddyfile{Colors.ENDC} at {Colors.ORANGE}{custom_caddyfile_path}{Colors.ENDC}...",
                source=RuntimeLogSource.BUILD,
            )

        caddyfile_path = os.path.normpath(
            os.path.join(details.temp_build_dir, "Caddyfile")
        )
        with open(caddyfile_path, "w") as file:
            file.write(caddyfile_contents)

        dockerfile_path = os.path.normpath(
            os.path.join(details.temp_build_dir, "Dockerfile")
        )
        with open(dockerfile_path, "w") as file:
            file.write(dockerfile_contents)

        await deployment_log(
            deployment=details.deployment,
            message=f"Succesfully generated files at {Colors.ORANGE}{caddyfile_path}{Colors.ENDC} and {Colors.ORANGE}{dockerfile_path}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )

        return StaticBuilderGeneratedResult(
            caddyfile_path=caddyfile_path,
            caddyfile_contents=caddyfile_contents,
            dockerfile_path=dockerfile_path,
            dockerfile_contents=dockerfile_contents,
            build_context_dir=details.temp_build_dir,
        )

    @activity.defn
    async def generate_default_files_for_nixpacks_builder(
        self, details: NixpacksBuilderDetails
    ) -> Optional[NixpacksBuilderGeneratedResult]:
        deployment = details.deployment
        service = deployment.service
        await deployment_log(
            deployment=details.deployment,
            message="Generating files for nixpacks builder...",
            source=RuntimeLogSource.BUILD,
        )

        build_directory = os.path.normpath(
            os.path.join(
                details.temp_build_dir,
                REPOSITORY_CLONE_LOCATION,
                details.builder_options.build_directory,
            )
        )
        args = ["nixpacks", "build", build_directory]
        cmd_lines = [f"Running {Colors.YELLOW}" + " ".join(args) + f" \\{Colors.ENDC}"]

        # pass all env variables
        parent_environment_variables = {
            env.key: env.value for env in service.environment.variables
        }

        build_envs = {**parent_environment_variables}
        build_envs.update(
            {
                env.key: replace_placeholders(
                    env.value, parent_environment_variables, "env"
                )
                for env in service.env_variables
            }
        )
        build_envs.update(
            {
                env.key: replace_placeholders(
                    env.value,
                    {
                        "slot": deployment.slot,
                        "hash": deployment.hash,
                    },
                    "deployment",
                )
                for env in service.system_env_variables
            }
        )

        for key, value in build_envs.items():
            args.extend(["-e", f"{key}={value}"])
            cmd_lines.append(f"{Colors.YELLOW}\t-e {key}={value} \\{Colors.ENDC}")

        # Use config file if it exists
        custom_config_file_path = os.path.normpath(
            os.path.join(details.temp_build_dir, build_directory, "nixpacks.toml")
        )
        use_custom_config_file = os.path.isfile(custom_config_file_path)
        if use_custom_config_file:
            args.extend(["--config", custom_config_file_path])
            cmd_lines.append(
                f"{Colors.YELLOW}\t--config {custom_config_file_path} \\{Colors.ENDC}"
            )

        # Custom build command
        if details.builder_options.custom_build_command is not None:
            args.extend(["--build-cmd", details.builder_options.custom_build_command])
            cmd_lines.append(
                f"{Colors.YELLOW}\t--build-cmd {details.builder_options.custom_build_command} \\{Colors.ENDC}"
            )

        # Custom install command
        if details.builder_options.custom_install_command is not None:
            args.extend(
                ["--install-cmd", details.builder_options.custom_install_command]
            )
            cmd_lines.append(
                f"{Colors.YELLOW}\t--install-cmd {details.builder_options.custom_install_command} \\{Colors.ENDC}"
            )

        # Custom start command
        if details.builder_options.custom_start_command is not None:
            args.extend(["--start-cmd", details.builder_options.custom_start_command])
            cmd_lines.append(
                f"{Colors.YELLOW}\t--start-cmd {details.builder_options.custom_start_command} \\{Colors.ENDC}"
            )

        # Include output
        args.extend(["-o", build_directory])
        cmd_lines.append(f"{Colors.YELLOW}\t-o {build_directory}{Colors.ENDC}")

        # Log executed command with all args
        await deployment_log(
            deployment=deployment,
            message=cmd_lines,
            source=RuntimeLogSource.BUILD,
        )
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
                message=f"Error when generating files for the nixpacks builder...",
                source=RuntimeLogSource.BUILD,
                error=True,
            )
            return

        # Copy `*.nix` files to build directory
        nixfiles = os.path.join(details.temp_build_dir, ".nixpacks", "*.nix")
        for file in glob.glob(nixfiles):
            shutil.copy(file, build_directory)

        # The Dockerfile is generated inside of the `.nixpacks`
        dockerfile_path = os.path.join(
            details.temp_build_dir, ".nixpacks", "Dockerfile"
        )

        await deployment_log(
            deployment=details.deployment,
            message=f"Succesfully generated Dockerfile file at {Colors.ORANGE}{dockerfile_path}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )
        return NixpacksBuilderGeneratedResult(
            build_context_dir=build_directory,
            dockerfile_path=dockerfile_path,
        )
