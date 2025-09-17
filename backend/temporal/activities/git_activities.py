import asyncio
import json
import shlex
from typing import Any, List, Optional, Set, cast
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
import os.path
import re
import requests

from rest_framework import status

with workflow.unsafe.imports_passed_through():
    from zane_api.models import Deployment, Environment, GitApp
    from zane_api.constants import HEAD_COMMIT
    import shutil
    from zane_api.git_client import (
        GitClient,
        GitCloneFailedError,
        GitCheckoutFailedError,
    )
    from ..helpers import (
        deployment_log,
        get_docker_client,
        get_resource_labels,
        get_env_network_resource_name,
        generate_caddyfile_for_static_website,
        get_buildkit_builder_resource_name,
        get_build_environment_variables_for_deployment,
        get_swarm_service_aliases_ips_on_network,
        get_swarm_service_name_for_deployment,
        empty_folder,
    )
    from search.dtos import RuntimeLogSource
    from zane_api.utils import (
        Colors,
        multiline_command,
        dict_sha256sum,
        generate_random_chars,
        replace_placeholders,
    )

    from zane_api.process import AyncSubProcessRunner
    from django.utils import timezone
    from django.db.models import OuterRef, Subquery


from copy import deepcopy

from ..shared import (
    DockerfileBuilderDetails,
    DockerfileBuilderGeneratedResult,
    EnvironmentDetails,
    GitBuildDetails,
    DeploymentDetails,
    GitCommitDetails,
    GitDeploymentDetailsWithCommitMessage,
    StaticBuilderDetails,
    StaticBuilderGeneratedResult,
    NixpacksBuilderGeneratedResult,
    GitCloneDetails,
    NixpacksBuilderDetails,
    RailpackBuilderDetails,
    RailpackBuilderGeneratedResult,
)
from ..constants import (
    DOCKERFILE_STATIC,
    REPOSITORY_CLONE_LOCATION,
    DOCKERFILE_NIXPACKS_STATIC,
    DOCKER_BINARY_PATH,
    NIXPACKS_BINARY_PATH,
    RAILPACK_BINARY_PATH,
    RAILPACK_STATIC_CONFIG,
    RAILPACK_CONFIG_BASE,
)
from zane_api.dtos import EnvVariableDto


class GitActivities:
    def __init__(self):
        self.docker_client = get_docker_client()
        self.git_client = GitClient()

    @activity.defn
    async def upsert_github_pull_request_comment(self, deployment: DeploymentDetails):
        current_deployment = (
            await Deployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service.id
            )
            .select_related(
                "service",
                "service__project",
                "service__environment",
                "service__environment__preview_metadata",
                "service__git_app",
                "service__git_app__github",
            )
            .afirst()
        )

        if current_deployment is None:
            return  # the service may have been deleted

        environment = current_deployment.service.environment
        git_app = current_deployment.service.git_app

        # service.
        if (
            git_app is None
            or git_app.github is None
            or not environment.is_preview
            or environment.preview_metadata is None
            or environment.preview_metadata.pr_number is None
            or environment.preview_metadata.pr_base_repo_url is None
        ):
            return

        preview_meta = environment.preview_metadata

        # 1️⃣ Define the API endpoint for creating a comment
        repo_url = environment.preview_metadata.pr_base_repo_url.removesuffix(".git")

        owner, repo = repo_url.removeprefix("https://github.com/").split("/")
        issue_number = environment.preview_metadata.pr_number

        # create issue comment
        url_base = f"https://api.github.com/repos/{owner}/{repo}/issues"

        # 2️⃣ Prepare the request
        headers = {
            "Authorization": f"Bearer {git_app.github.get_access_token()}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "body": await current_deployment.aget_pull_request_deployment_comment_body()
        }

        # 3️⃣ Make the request
        if preview_meta.pr_comment_id is not None:
            url = url_base + f"/comments/{preview_meta.pr_comment_id}"
            response = requests.patch(url, headers=headers, json=payload)

            # we will need to recreate the PR comment
            if response.status_code == status.HTTP_404_NOT_FOUND:
                url = url_base + f"/{issue_number}/comments"
                response = requests.post(url, headers=headers, json=payload)

        else:
            url = url_base + f"/{issue_number}/comments"
            response = requests.post(url, headers=headers, json=payload)

        # 4️⃣ Check the response
        if status.is_success(response.status_code):
            data = response.json()
            print(
                "Comment created:",
                data["html_url"],
            )
            print("Comment Body:\n", data["body"])

            # Update Preview metadata with the comment ID
            preview_meta.pr_comment_id = data["id"]
            await preview_meta.asave()

            return dict(status_code=response.status_code, data=data, url=url)
        else:
            text = response.text
            print(
                f"Error when trying to upser a PR comment for the {deployment.service.slug=} on the PR #{issue_number}({repo_url}/pulls/{issue_number}): ",
                response.status_code,
                text,
            )
            return dict(status_code=response.status_code, data=text, url=url)

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
            message=f"Cleaning up temporary build directory at {Colors.ORANGE}{details.tmp_dir}{Colors.ENDC}...",
            source=RuntimeLogSource.BUILD,
        )
        shutil.rmtree(details.tmp_dir, ignore_errors=True)
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
        cancel_event = asyncio.Event()
        build_location = os.path.join(details.tmp_dir, REPOSITORY_CLONE_LOCATION)
        try:

            async def send_heartbeat():
                """
                We want this activity to be cancellable,
                for activities to be cancellable, they need to send regular heartbeats:
                https://docs.temporal.io/develop/python/cancellation#cancel-activity
                """
                while True:
                    activity.heartbeat(
                        "Heartbeat from `clone_repository_and_checkout_to_commit()`..."
                    )
                    await asyncio.sleep(0.1)

            heartbeat_task = asyncio.create_task(send_heartbeat())

            service = details.deployment.service
            deployment = details.deployment

            git_deployment_query = Deployment.objects.filter(
                hash=deployment.hash, service_id=deployment.service.id
            ).select_related("service")
            if not await git_deployment_query.aexists():
                raise ApplicationError(
                    "Cannot update a non existent deployment.",
                    non_retryable=True,
                )

            git_deployment = await git_deployment_query.aget()
            git_deployment.status = Deployment.DeploymentStatus.BUILDING
            await git_deployment.asave(update_fields=["status", "updated_at"])

            print(f"Emptying folder {Colors.ORANGE}{details.tmp_dir}{Colors.ENDC}...")
            empty_task = asyncio.create_task(
                asyncio.to_thread(empty_folder, details.tmp_dir)
            )
            done_first, _ = await asyncio.wait(
                [empty_task, heartbeat_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if empty_task in done_first:
                print(
                    f"Folder {Colors.ORANGE}{details.tmp_dir}{Colors.ENDC} emptied succesfully ✅"
                )
            else:
                empty_task.cancel()
                await empty_task
                return None

            await deployment_log(
                deployment=details.deployment,
                message=f"Cloning repository {Colors.ORANGE}{service.repository_url}{Colors.ENDC} to {Colors.ORANGE}{build_location}{Colors.ENDC}...",
                source=RuntimeLogSource.BUILD,
            )
            try:

                async def message_handler(message: str, error: bool = False):
                    await deployment_log(
                        deployment=details.deployment,
                        message=message,
                        source=RuntimeLogSource.BUILD,
                        error=error,
                    )

                repo_url = cast(str, service.repository_url)
                if service.git_app is not None:
                    gitapp = (
                        await GitApp.objects.filter(id=service.git_app.id)
                        .select_related("github", "gitlab")
                        .aget()
                    )
                    if gitapp.github is not None:
                        repo_url = gitapp.github.get_authenticated_repository_url(
                            repo_url
                        )
                    elif gitapp.gitlab is not None:
                        repo_url = await gitapp.gitlab.aget_authenticated_repository_url(
                            repo_url
                        )

                clone_task = asyncio.create_task(
                    self.git_client.aclone_repository(
                        url=repo_url,
                        dest_path=build_location,
                        branch=service.branch_name,  # type: ignore - this is defined in the case of git services
                        message_handler=message_handler,
                        cancel_event=cancel_event,
                    )
                )
                done_first, _ = await asyncio.wait(
                    [clone_task, heartbeat_task], return_when=asyncio.FIRST_COMPLETED
                )
                if clone_task in done_first:
                    repo = clone_task.result()
                    print("Clone task finished first ?")
                else:
                    clone_task.cancel()
                    await clone_task
                    return None
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
                    checkout_task = asyncio.create_task(
                        asyncio.to_thread(
                            self.git_client.checkout_repository,
                            repo,
                            deployment.commit_sha or HEAD_COMMIT,
                        )
                    )

                    done_first, _ = await asyncio.wait(
                        [checkout_task, heartbeat_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if checkout_task in done_first:
                        commit = checkout_task.result()
                        print("Checkout task finished first ?")
                    else:
                        checkout_task.cancel()
                        await checkout_task
                        return None
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

        if (
            git_deployment.commit_message is None
            or git_deployment.commit_author_name is None
        ):
            git_deployment.commit_message = details.commit.commit_message
            git_deployment.commit_author_name = details.commit.author_name
            await git_deployment.asave(
                update_fields=["commit_message", "commit_author_name", "updated_at"]
            )

    @activity.defn
    async def create_buildkit_builder_for_env(self, payload: DeploymentDetails):
        await deployment_log(
            deployment=payload,
            message="Creating Buildkit builder for the environment...",
            source=RuntimeLogSource.BUILD,
        )
        builder_name = get_buildkit_builder_resource_name(
            payload.service.environment.id
        )
        process = await asyncio.create_subprocess_exec(
            DOCKER_BINARY_PATH, "buildx", "inspect", builder_name
        )
        await process.communicate()

        if process.returncode == 0:
            await deployment_log(
                deployment=payload,
                message=f"Builder {Colors.ORANGE}{builder_name}{Colors.ENDC} already exists, skipping creation ✅",
                source=RuntimeLogSource.BUILD,
            )
            return

        network = get_env_network_resource_name(
            payload.service.environment.id, project_id=payload.service.project_id
        )

        cmd_args = [
            DOCKER_BINARY_PATH,
            "buildx",
            "create",
            "--name",
            builder_name,
            "--driver",
            "docker-container",
            "--driver-opt",
            f"network={network}",
        ]
        cmd_string = multiline_command(shlex.join(cmd_args))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        for index, msg in enumerate(log_message.splitlines()):
            await deployment_log(
                deployment=payload,
                message=f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg,
                source=RuntimeLogSource.BUILD,
            )

        process = await asyncio.create_subprocess_shell(
            shlex.join(cmd_args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        info_lines = stdout.decode().splitlines()
        error_lines = stderr.decode().splitlines()
        if len(info_lines) > 0:
            await deployment_log(
                deployment=payload,
                message=info_lines,
                source=RuntimeLogSource.BUILD,
            )
        if len(error_lines) > 0:
            await deployment_log(
                deployment=payload,
                message=error_lines,
                source=RuntimeLogSource.BUILD,
                error=True,
            )
        if process.returncode != 0:
            await deployment_log(
                deployment=payload,
                message="Error creating builder for the app",
                source=RuntimeLogSource.BUILD,
                error=True,
            )
            raise Exception("Error when crating the builder for the app")
        await deployment_log(
            deployment=payload,
            message=f"Builder {Colors.ORANGE}{builder_name}{Colors.ENDC} created sucessfully ✅",
            source=RuntimeLogSource.BUILD,
        )

    @activity.defn
    async def delete_buildkit_builder_for_env(self, payload: EnvironmentDetails):
        builder_name = get_buildkit_builder_resource_name(payload.id)
        print(
            f"Deleting buildkit builder {Colors.ORANGE}{builder_name}{Colors.ENDC}..."
        )
        process = await asyncio.create_subprocess_exec(
            DOCKER_BINARY_PATH, "buildx", "inspect", builder_name
        )
        await process.communicate()

        if process.returncode != 0:
            print(
                f"Buildkit builder {Colors.ORANGE}{builder_name}{Colors.ENDC} has already been deleted, skipping deletion ✅"
            )
            return None

        process = await asyncio.create_subprocess_exec(
            DOCKER_BINARY_PATH,
            "buildx",
            "rm",
            "--force",
            builder_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, stderr = await process.communicate()
        info_lines = stdout.decode()
        error_lines = stderr.decode()
        if info_lines:
            print(info_lines)
        if error_lines:
            print(error_lines)
        if process.returncode != 0:
            raise Exception("Error when crating the builder for the app")
        print(
            f"Builder {Colors.ORANGE}{builder_name}{Colors.ENDC} deleted sucessfully ✅"
        )
        return builder_name

    @activity.defn
    async def build_service_with_dockerfile(
        self, details: GitBuildDetails
    ) -> Optional[str]:
        cancel_event = asyncio.Event()
        heartbeat_task = None

        async def send_heartbeat():
            """
            We want this activity to be cancellable,
            for activities to be cancellable, they need to send regular heartbeats:
            https://docs.temporal.io/develop/python/cancellation#cancel-activity
            """
            while True:
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

            git_deployment.build_started_at = timezone.now()
            await git_deployment.asave(update_fields=["build_started_at", "updated_at"])

            try:
                # Get build env variables
                if details.default_env_variables is not None:
                    build_envs = {
                        env.key: env.value for env in details.default_env_variables
                    }
                else:
                    build_envs = get_build_environment_variables_for_deployment(
                        deployment
                    )

                # Always force color
                build_envs["FORCE_COLOR"] = "true"

                # construct arguments
                builder_name = get_buildkit_builder_resource_name(
                    service.environment.id
                )

                # Construct each line of the build command as a separate string
                docker_build_command = [DOCKER_BINARY_PATH, "buildx", "build"]
                docker_build_command.extend(["--builder", builder_name])
                docker_build_command.extend(["-t", details.image_tag])
                docker_build_command.extend(["-f", details.dockerfile_path])

                # Here, since the buildkit builder uses a docker container driver,
                # its host network is the network of the builder
                # ref: https://github.com/docker/buildx/issues/2306#issuecomment-1979915930
                docker_build_command.extend(["--network=host"])

                # limit CPU to ~33% max usage
                docker_build_command.append("--cpu-shares=342")
                # disable cache ?
                if deployment.ignore_build_cache:
                    docker_build_command.append("--no-cache")

                # Append build arguments, each on its own line
                for key, value in build_envs.items():
                    docker_build_command.extend(["--build-arg", f"{key}={value}"])

                if details.build_stage_target:
                    docker_build_command.extend(
                        ["--target", details.build_stage_target]
                    )

                # Append label arguments
                resource_labels = get_resource_labels(
                    service.project_id, parent=service.id
                )
                for k, v in resource_labels.items():
                    docker_build_command.extend(["--label", f"{k}={v}"])

                # load the image to the local images
                docker_build_command.extend(
                    ["--output", f"type=docker,name={details.image_tag}"]
                )
                # Finally, add the build context directory
                docker_build_command.append(details.build_context_dir)

                await deployment_log(
                    deployment=deployment,
                    message="===================== RUNNING DOCKER BUILD ===========================",
                    source=RuntimeLogSource.BUILD,
                )

                docker_build_command = shlex.join(docker_build_command)
                cmd_string = multiline_command(docker_build_command)
                log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
                for index, msg in enumerate(log_message.splitlines()):
                    await deployment_log(
                        deployment=deployment,
                        message=(
                            f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg
                        ),
                        source=RuntimeLogSource.BUILD,
                    )

                # ====== DOCKER BUILD COMMAND ====
                async def message_handler(message: str):
                    is_error_message = message.startswith("ERROR:")
                    await deployment_log(
                        deployment=details.deployment,
                        message=(
                            f"{Colors.RED}{message}{Colors.ENDC}"
                            if is_error_message
                            else f"{Colors.BLUE}{message}{Colors.ENDC}"
                        ),
                        source=RuntimeLogSource.BUILD,
                        error=is_error_message,
                    )
                    match = re.search(
                        r"(^Successfully built |sha256:)([0-9a-f]+)",
                        message,
                    )
                    if match:
                        return match.group(2)  # Image ID

                docker_build_process = AyncSubProcessRunner(
                    command=docker_build_command,
                    cancel_event=cancel_event,
                    operation_name="docker build",
                    output_handler=message_handler,
                )
                image_id = None
                build_image_task = asyncio.create_task(docker_build_process.run())

                task_set.add(build_image_task)
                done_first, _ = await asyncio.wait(
                    task_set, return_when=asyncio.FIRST_COMPLETED
                )
                if build_image_task in done_first:
                    exit_code, image_id = build_image_task.result()
                    if exit_code != 0:
                        image_id = None
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

                await deployment_log(
                    deployment=details.deployment,
                    message=f"Service build complete. Tagged as {Colors.ORANGE}{details.image_tag} ({image_id}){Colors.ENDC} ✅",
                    source=RuntimeLogSource.BUILD,
                )
                return image_id
            finally:
                await deployment_log(
                    deployment=deployment,
                    message="======================== DOCKER BUILD FINISHED  ========================",
                    source=RuntimeLogSource.BUILD,
                )
                git_deployment.build_finished_at = timezone.now()
                await git_deployment.asave(
                    update_fields=["build_finished_at", "updated_at"]
                )
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()

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
        build_envs = get_build_environment_variables_for_deployment(details.deployment)

        build_envs["FORCE_COLOR"] = "true"
        env_lines = [f"{key}={shlex.quote(value)}" for key, value in build_envs.items()]
        env_file_contents = "\n".join(env_lines)

        # Add `.env` in the build context directory to be loaded by the Dockerfile if possible
        env_file_path = os.path.join(build_context_dir, ".env")
        with open(env_file_path, "w") as file:
            file.write(env_file_contents)

        return DockerfileBuilderGeneratedResult(
            build_context_dir=build_context_dir,
            dockerfile_path=dockerfile_path,
            env_file_path=env_file_path,
            env_file_contents=env_file_contents,
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
            dict(publish={"dir": publish_directory}),
        )

        # Use a custom Caddyfile if it exists
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

        # Create nixpacks folder if it doesn't exist
        nixpacks_plan_path = os.path.join(build_directory, ".nixpacks", "plan.json")
        os.makedirs(os.path.dirname(nixpacks_plan_path), exist_ok=True)

        # ====== PLAN PROCESS ======
        nixpacks_plan_command_args = [
            NIXPACKS_BINARY_PATH,
            "plan",
        ]

        build_envs = get_build_environment_variables_for_deployment(deployment)
        build_envs["FORCE_COLOR"] = "true"

        # Disable mount cache in nixpacks
        if deployment.ignore_build_cache:
            build_envs["NIXPACKS_NO_CACHE"] = "true"

        for key, value in build_envs.items():
            nixpacks_plan_command_args.extend(["--env", f"{key}={value}"])

        # Use config file if it exists
        custom_config_file_path = os.path.normpath(
            os.path.join(build_directory, "nixpacks.toml")
        )
        use_custom_config_file = os.path.isfile(custom_config_file_path)
        if use_custom_config_file:
            nixpacks_plan_command_args.extend(["--config", custom_config_file_path])

        # Custom build command
        if details.builder_options.custom_build_command is not None:
            nixpacks_plan_command_args.extend(
                ["--build-cmd", details.builder_options.custom_build_command]
            )

        # Custom install command
        if details.builder_options.custom_install_command is not None:
            nixpacks_plan_command_args.extend(
                ["--install-cmd", details.builder_options.custom_install_command]
            )

        # Custom start command
        if details.builder_options.custom_start_command is not None:
            nixpacks_plan_command_args.extend(
                ["--start-cmd", details.builder_options.custom_start_command]
            )

        # Include build directory
        nixpacks_plan_command_args.append(build_directory)

        # Log executed command with all args
        cmd_string = multiline_command(shlex.join(nixpacks_plan_command_args))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        for index, msg in enumerate(log_message.splitlines()):
            await deployment_log(
                deployment=deployment,
                message=(f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg),
                source=RuntimeLogSource.BUILD,
            )

        # Execute process
        with open(nixpacks_plan_path, "w") as file:
            process = await asyncio.create_subprocess_shell(
                shlex.join(nixpacks_plan_command_args),
                stdout=file,
                stderr=asyncio.subprocess.PIPE,
            )
        stdout, stderr = await process.communicate()
        error_lines = stderr.decode().splitlines()
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
                message="Error when generating files for the nixpacks builder...",
                source=RuntimeLogSource.BUILD,
                error=True,
            )
            return

        env_variables: List[EnvVariableDto] = []
        with open(nixpacks_plan_path, "r") as file:
            data = json.loads(file.read())
            nixpacks_plan_contents = data

            for key, value in data["variables"].items():
                env_variables.append(EnvVariableDto(key=key, value=value))

        # ====== BUILD PROCESS ======
        # Build command args
        nixpacks_build_command_args = [
            NIXPACKS_BINARY_PATH,
            "build",
            "--config",
            nixpacks_plan_path,
            "--no-error-without-start",
            "--out",
            build_directory,
            build_directory,
        ]

        # Log executed command with all args
        cmd_string = multiline_command(shlex.join(nixpacks_build_command_args))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        for index, msg in enumerate(log_message.splitlines()):
            await deployment_log(
                deployment=deployment,
                message=(f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg),
                source=RuntimeLogSource.BUILD,
            )

        process = await asyncio.create_subprocess_exec(
            *nixpacks_build_command_args,
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
                message="Error when generating files for the nixpacks builder...",
                source=RuntimeLogSource.BUILD,
                error=True,
            )
            return

        # The Dockerfile is generated inside of the `.nixpacks`
        dockerfile_path = os.path.join(build_directory, ".nixpacks", "Dockerfile")
        # Read the Dockerfile
        with open(dockerfile_path, "r") as file:
            dockerfile_contents = file.read()
        caddyfile_path = None
        caddyfile_contents = None
        if details.builder_options.is_static:
            await deployment_log(
                deployment=details.deployment,
                message=f"Generating default {Colors.ORANGE}Caddyfile{Colors.ENDC} for Nixpacks static builder...",
                source=RuntimeLogSource.BUILD,
            )
            # generate static files
            caddyfile_contents = generate_caddyfile_for_static_website(
                details.builder_options
            )
            # Use the custom Caddyfile if it exists
            caddyfile_path = os.path.normpath(
                os.path.join(
                    build_directory,
                    "Caddyfile",
                )
            )
            use_custom_caddyfile = os.path.isfile(caddyfile_path)
            if use_custom_caddyfile:
                with open(caddyfile_path, "r") as file:
                    caddyfile_contents = file.read()

                await deployment_log(
                    deployment=details.deployment,
                    message=f"Using custom {Colors.ORANGE}Caddyfile{Colors.ENDC} at {Colors.ORANGE}{caddyfile_path}{Colors.ENDC}...",
                    source=RuntimeLogSource.BUILD,
                )
            else:
                # Copy caddyfile contents
                with open(caddyfile_path, "w") as file:
                    file.write(caddyfile_contents)

            # Make the first image as the builder
            lines = dockerfile_contents.splitlines()
            lines[0] = lines[0] + " AS builder"
            full_dockerfile_contents = "\n".join(lines)
            publish_directory = os.path.normpath(
                os.path.join(
                    "/app/", details.builder_options.publish_directory.rstrip("/")
                )
            )
            full_dockerfile_contents += replace_placeholders(
                DOCKERFILE_NIXPACKS_STATIC,
                dict(publish={"dir": f"{publish_directory}/"}),
            )
            # Overwrite the Dockerfile
            with open(dockerfile_path, "w") as file:
                file.write(full_dockerfile_contents)
            dockerfile_contents = full_dockerfile_contents

        await deployment_log(
            deployment=details.deployment,
            message=f"Succesfully generated Dockerfile file at {Colors.ORANGE}{dockerfile_path}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )
        return NixpacksBuilderGeneratedResult(
            build_context_dir=build_directory,
            dockerfile_path=dockerfile_path,
            dockerfile_contents=dockerfile_contents,
            caddyfile_path=caddyfile_path,
            caddyfile_contents=caddyfile_contents,
            variables=env_variables,
            nixpacks_plan_contents=nixpacks_plan_contents,
        )

    @activity.defn
    async def generate_default_files_for_railpack_builder(
        self, details: RailpackBuilderDetails
    ) -> Optional[RailpackBuilderGeneratedResult]:
        deployment = details.deployment
        await deployment_log(
            deployment=details.deployment,
            message="Generating files for railpack builder...",
            source=RuntimeLogSource.BUILD,
        )

        build_directory = os.path.normpath(
            os.path.join(
                details.temp_build_dir,
                REPOSITORY_CLONE_LOCATION,
                details.builder_options.build_directory,
            )
        )

        # Create railpack folder if it doesn't exist
        railpack_plan_path = os.path.join(build_directory, ".railpack", "plan.json")
        os.makedirs(os.path.dirname(railpack_plan_path), exist_ok=True)

        caddyfile_contents = None
        # Create railpack static config
        railpack_custom_config_path = os.path.normpath(
            os.path.join(
                build_directory,
                "railpack.json",
            )
        )
        railpack_custom_config_contents: dict[str, Any] = RAILPACK_CONFIG_BASE

        # Custom install command
        if details.builder_options.custom_install_command is not None:
            railpack_custom_config_contents = {
                **railpack_custom_config_contents,
                "steps": {
                    "install": {
                        "commands": [
                            {"dest": ".", "src": "."},
                            details.builder_options.custom_install_command,
                        ]
                    }
                },
            }

        if details.builder_options.is_static:
            await deployment_log(
                deployment=details.deployment,
                message=f"Generating default {Colors.ORANGE}Caddyfile{Colors.ENDC} for Railpack static builder...",
                source=RuntimeLogSource.BUILD,
            )

            # generate static files
            caddyfile_contents = generate_caddyfile_for_static_website(
                details.builder_options
            )
            # Use the custom Caddyfile if it exists
            custom_caddyfile_path = os.path.normpath(
                os.path.join(
                    build_directory,
                    "Caddyfile",
                )
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

                railpack_static_config = deepcopy(RAILPACK_STATIC_CONFIG)
                # fill in caddyfile content
                railpack_static_config["steps"]["caddy"]["assets"][
                    "Caddyfile"
                ] = caddyfile_contents

                # export the dist output
                publish_dir = os.path.normpath(
                    os.path.join("/app", details.builder_options.publish_directory)
                )
                railpack_static_config["steps"]["build:export"]["deployOutputs"][0][
                    "include"
                ] = [publish_dir]
                # Set the public directory variable for the `Caddyfile`
                railpack_static_config["deploy"]["variables"][
                    "PUBLIC_ROOT"
                ] = publish_dir

                for key in railpack_static_config:
                    match key:
                        case "steps":
                            railpack_custom_config_contents["steps"] = {
                                **railpack_custom_config_contents.get(key, {}),
                                **railpack_static_config[key],
                            }
                        case _:
                            railpack_custom_config_contents[key] = (
                                railpack_static_config[key]
                            )

            await deployment_log(
                deployment=details.deployment,
                message=f"Succesfully generated railpack config for static files at {Colors.ORANGE}{railpack_custom_config_path}{Colors.ENDC} ✅",
                source=RuntimeLogSource.BUILD,
            )

        # create railpack config file
        with open(railpack_custom_config_path, "w") as file:
            file.write(json.dumps(railpack_custom_config_contents))

        # ====== PREPARE COMMAND ======
        railpack_prepare_command_args = [
            "FORCE_COLOR=true",
            RAILPACK_BINARY_PATH,
            "prepare",
        ]

        build_envs = get_build_environment_variables_for_deployment(deployment)
        for key, value in build_envs.items():
            railpack_prepare_command_args.extend(["--env", f"{key}={value}"])

        # Always force color
        railpack_prepare_command_args.extend(["--env", "FORCE_COLOR=true"])

        if deployment.ignore_build_cache:
            # We force the reevaluation of the cache by adding a random key in the build envs
            railpack_prepare_command_args.extend(
                ["--env", f"__ZANE_RANDOM_SEED={generate_random_chars(64)}"]
            )

        # Custom build command
        if details.builder_options.custom_build_command is not None:
            railpack_prepare_command_args.extend(
                ["--build-cmd", details.builder_options.custom_build_command]
            )

        # Custom start command
        if details.builder_options.custom_start_command is not None:
            railpack_prepare_command_args.extend(
                ["--start-cmd", details.builder_options.custom_start_command]
            )

        railpack_prepare_command_args.extend(["--config-file", "railpack.json"])

        # Output `plan.json`
        railpack_prepare_command_args.extend(["--plan-out", railpack_plan_path])

        # Include build directory
        railpack_prepare_command_args.append(build_directory)

        # Log executed command with all args
        cmd_string = multiline_command(shlex.join(railpack_prepare_command_args))
        log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
        for index, msg in enumerate(log_message.splitlines()):
            await deployment_log(
                deployment=deployment,
                message=(f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg),
                source=RuntimeLogSource.BUILD,
            )

        # Execute process
        process = await asyncio.create_subprocess_shell(
            shlex.join(railpack_prepare_command_args),
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
                message="Error when generating files for the railpack builder...",
                source=RuntimeLogSource.BUILD,
                error=True,
            )
            return

        with open(railpack_plan_path, "r") as file:
            data = json.loads(file.read())
            railpack_plan_contents = data

        await deployment_log(
            deployment=details.deployment,
            message=f"Succesfully generated railpack plan file at {Colors.ORANGE}{railpack_plan_path}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )
        return RailpackBuilderGeneratedResult(
            railpack_custom_config_contents=railpack_custom_config_contents,
            railpack_custom_config_path=railpack_custom_config_path,
            build_context_dir=build_directory,
            caddyfile_contents=caddyfile_contents,
            railpack_plan_path=railpack_plan_path,
            railpack_plan_contents=railpack_plan_contents,
        )

    @activity.defn
    async def build_service_with_railpack_dockerfile(
        self, details: GitBuildDetails
    ) -> Optional[str]:
        cancel_event = asyncio.Event()
        heartbeat_task = None

        async def send_heartbeat():
            """
            We want this activity to be cancellable,
            for activities to be cancellable, they need to send regular heartbeats:
            https://docs.temporal.io/develop/python/cancellation#cancel-activity
            """
            while True:
                activity.heartbeat(
                    "Heartbeat from `build_service_with_railpack_dockerfile()`..."
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

            git_deployment.build_started_at = timezone.now()
            await git_deployment.asave(update_fields=["build_started_at", "updated_at"])

            current_env = await Environment.objects.aget(pk=service.environment.id)

            current_network_name = get_env_network_resource_name(
                current_env.id, service.project_id
            )
            service_names = []
            deployment_queryset = Deployment.objects.filter(
                service_id=OuterRef("pk"), is_current_production=True
            ).order_by("-updated_at")
            async for service in (
                current_env.services.filter()
                .exclude(id=service.id)
                .annotate(
                    production_deployment_hash=Subquery(
                        deployment_queryset.values("hash")[:1]
                    )
                )
            ):
                service_name = get_swarm_service_name_for_deployment(service.production_deployment_hash, service.project_id, service.id)  # type: ignore
                service_names.append(service_name)

            service_ip_aliases_map = get_swarm_service_aliases_ips_on_network(
                service_names, current_network_name
            )

            try:
                # Get build env variables
                build_envs = get_build_environment_variables_for_deployment(deployment)

                # This is to fix a BUG with railpack not correctly setting hosts in the build process of buildkit
                # to circumvent this error, we replace the network aliases of services by their ips in each env variable
                # ref: https://github.com/railwayapp/railpack/issues/145
                for env in build_envs:
                    for alias in service_ip_aliases_map:
                        if alias in build_envs[env]:
                            global_alias = f"{alias}.{details.deployment.service.environment.id.replace(Environment.ID_PREFIX, '')}"
                            build_envs[env] = (
                                build_envs[env]
                                # also replace their internal FQDN network aliases
                                .replace(
                                    f"{alias}.zaneops.internal",
                                    service_ip_aliases_map[alias],
                                )
                                .replace(alias, service_ip_aliases_map[alias])
                                # also replace their internal FQDN global network aliases
                                .replace(
                                    global_alias,
                                    service_ip_aliases_map[alias],
                                )
                                .replace(
                                    f"{global_alias}.zaneops.internal",
                                    service_ip_aliases_map[alias],
                                )
                            )

                # Always force color
                build_envs["FORCE_COLOR"] = "true"

                if details.deployment.ignore_build_cache:
                    # We force the reevaluation of the cache by adding a random key in the build envs
                    build_envs["__ZANE_RANDOM_SEED"] = generate_random_chars(64)

                # construct arguments
                builder_name = get_buildkit_builder_resource_name(
                    service.environment.id
                )

                # Construct each line of the build command as a separate string
                docker_build_command = []
                docker_build_command.extend([DOCKER_BINARY_PATH, "buildx", "build"])
                docker_build_command.extend(["--builder", builder_name])

                # Here, since the buildkit builder uses a docker container driver,
                # its host network is the network of the builder
                # ref: https://github.com/docker/buildx/issues/2306#issuecomment-1979915930
                docker_build_command.extend(["--network=host"])

                # limit CPU to ~33% max usage
                docker_build_command.append("--cpu-shares=342")

                # disable cache ?
                if deployment.ignore_build_cache:
                    docker_build_command.append("--no-cache")
                    docker_build_command.extend(
                        ["--build-arg", f"cache-key={generate_random_chars(20)}"]
                    )

                # Use railway-frontend build frontend
                docker_build_command.extend(
                    [
                        "--build-arg",
                        "BUILDKIT_SYNTAX=ghcr.io/railwayapp/railpack-frontend:v$RAILPACK_VERSION",
                    ]
                )

                # Add secret hash of all env variables
                docker_build_command.extend(
                    ["--build-arg", f"secrets-hash={dict_sha256sum(build_envs)}"]
                )

                for env_name in build_envs:
                    docker_build_command.extend(
                        ["--secret", f"id={env_name},env={env_name}"]
                    )

                # Append label arguments
                resource_labels = get_resource_labels(
                    service.project_id, parent=service.id
                )
                for k, v in resource_labels.items():
                    docker_build_command.extend(["--label", f"{k}={v}"])

                # load the image to the local images
                docker_build_command.extend(
                    ["--output", f"type=docker,name={details.image_tag}"]
                )

                # Add the tag and dockerfile
                docker_build_command.extend(["-t", details.image_tag])
                docker_build_command.extend(["-f", details.dockerfile_path])

                # Finally, add the build context directory
                docker_build_command.append(details.build_context_dir)

                await deployment_log(
                    deployment=deployment,
                    message="===================== RUNNING DOCKER BUILD ===========================",
                    source=RuntimeLogSource.BUILD,
                )

                def safe_quote(arg: str) -> str:
                    return (
                        arg if arg.startswith("BUILDKIT_SYNTAX=") else shlex.quote(arg)
                    )

                docker_build_command = " ".join(
                    safe_quote(arg) for arg in docker_build_command
                )
                env_args = [
                    f"{env}={shlex.quote(value)}" for env, value in build_envs.items()
                ]
                docker_build_command = " ".join([*env_args, docker_build_command])

                cmd_string = multiline_command(
                    docker_build_command, ignore_contains="BUILDKIT_SYNTAX="
                )
                log_message = f"Running {Colors.YELLOW}{cmd_string}{Colors.ENDC}"
                for index, msg in enumerate(log_message.splitlines()):
                    await deployment_log(
                        deployment=deployment,
                        message=(
                            f"{Colors.YELLOW}{msg}{Colors.ENDC}" if index > 0 else msg
                        ),
                        source=RuntimeLogSource.BUILD,
                    )

                # ====== DOCKER BUILD COMMAND ====
                async def message_handler(message: str):
                    is_error_message = message.startswith("ERROR:")
                    await deployment_log(
                        deployment=details.deployment,
                        message=(
                            f"{Colors.RED}{message}{Colors.ENDC}"
                            if is_error_message
                            else f"{Colors.BLUE}{message}{Colors.ENDC}"
                        ),
                        source=RuntimeLogSource.BUILD,
                        error=is_error_message,
                    )
                    match = re.search(
                        r"(^Successfully built |sha256:)([0-9a-f]+)",
                        message,
                    )
                    if match:
                        return match.group(2)  # Image ID

                docker_build_process = AyncSubProcessRunner(
                    command=docker_build_command,
                    cancel_event=cancel_event,
                    operation_name="docker build",
                    output_handler=message_handler,
                )
                image_id = None
                build_image_task = asyncio.create_task(docker_build_process.run())

                task_set.add(build_image_task)
                done_first, _ = await asyncio.wait(
                    task_set, return_when=asyncio.FIRST_COMPLETED
                )
                if build_image_task in done_first:
                    exit_code, image_id = build_image_task.result()
                    if exit_code != 0:
                        image_id = None
                    print("`build_image_task()` finished first")
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

                await deployment_log(
                    deployment=details.deployment,
                    message=f"Service build complete. Tagged as {Colors.ORANGE}{details.image_tag} ({image_id}){Colors.ENDC} ✅",
                    source=RuntimeLogSource.BUILD,
                )
                return image_id
            finally:
                await deployment_log(
                    deployment=deployment,
                    message="======================== DOCKER BUILD FINISHED  ========================",
                    source=RuntimeLogSource.BUILD,
                )
                git_deployment.build_finished_at = timezone.now()
                await git_deployment.asave(
                    update_fields=["build_finished_at", "updated_at"]
                )
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
