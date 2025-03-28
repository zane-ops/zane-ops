import itertools
from typing import Optional, cast
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
from typing import Any
import re

with workflow.unsafe.imports_passed_through():
    import docker.errors
    from ...models import Deployment, Service
    from docker.utils.json_stream import json_stream
    import shutil
    from ...git_client import GitClient, GitCloneFailedError, GitCheckoutFailedError
    from ..helpers import (
        deployment_log,
        get_docker_client,
        get_resource_labels,
        replace_env_variables,
        get_env_network_resource_name,
    )
    from search.dtos import RuntimeLogSource
    from ...utils import Colors
    from django.utils import timezone

from ..shared import (
    GitBuildDetails,
    DeploymentDetails,
    GitCommitDetails,
    GitDeploymentDetailsWithCommitMessage,
)

from ...dtos import DockerfileBuilderOptions


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
    async def cleanup_temporary_directory_for_build(self, details: GitBuildDetails):
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
        self, details: GitBuildDetails
    ) -> Optional[GitCommitDetails]:
        service = details.deployment.service
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

        git_deployment.status = Deployment.DeploymentStatus.BUILDING
        await git_deployment.asave()

        await deployment_log(
            deployment=details.deployment,
            message=f"Cloning repository {Colors.ORANGE}{service.repository_url}{Colors.ENDC} to {Colors.ORANGE}{details.location}{Colors.ENDC}...",
            source=RuntimeLogSource.BUILD,
        )
        try:
            repo = self.git_client.clone_repository(
                url=service.repository_url,  # type: ignore - this is defined in the case of git services
                dest_path=details.location,
                branch=service.branch_name,  # type: ignore - this is defined in the case of git services
            )
        except GitCloneFailedError as e:
            await deployment_log(
                deployment=details.deployment,
                message=f"Failed to clone the repository to {Colors.ORANGE}{details.location}{Colors.ENDC} ❌: {Colors.GREY}{e}{Colors.ENDC}",
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
        deployment = details.deployment
        service = deployment.service

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

        git_deployment.build_started_at = timezone.now()
        await git_deployment.asave()

        base_image = service.id.replace(Service.ID_PREFIX, "").lower()
        try:
            builder_options = cast(
                DockerfileBuilderOptions, service.dockerfile_builder_options
            )

            build_context_dir = os.path.normpath(
                os.path.join(details.location, builder_options.build_context_dir)
            )
            dockerfile_path = os.path.normpath(
                os.path.join(details.location, builder_options.dockerfile_path)
            )

            parent_environment_variables = {
                env.key: env.value for env in service.environment.variables
            }

            build_envs = {**parent_environment_variables}
            build_envs.update(
                {
                    env.key: replace_env_variables(
                        env.value, parent_environment_variables, "env"
                    )
                    for env in service.env_variables
                }
            )
            build_envs.update(
                {
                    env.key: replace_env_variables(
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
            cmd_lines.append(f"-f {dockerfile_path} \\")

            # Append build arguments, each on its own line
            for key, value in build_envs.items():
                cmd_lines.append(f"--build-arg {key}={value} \\")

            if builder_options.build_stage_target:
                cmd_lines.append(f"--target {builder_options.build_stage_target} \\")
            if deployment.ignore_build_cache:
                cmd_lines.append("--no-cache \\")

            # Append label arguments
            resource_labels = get_resource_labels(service.project_id, parent=service.id)
            for k, v in resource_labels.items():
                cmd_lines.append(f"--label {k}={v} \\")

            cmd_lines.append(f"--network={build_network} \\")
            cmd_lines.append(
                f"--cpu-shares=512 \\ {Colors.GREY}# limit cpu usage to 50%{Colors.ENDC}"
            )
            # Finally, add the build context directory
            cmd_lines.append(build_context_dir)

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
            build_output = self.docker_client.api.build(
                path=build_context_dir,
                dockerfile=dockerfile_path,
                tag=deployment.image_tag,
                buildargs=build_envs,
                target=builder_options.build_stage_target,
                rm=True,
                labels=get_resource_labels(service.project_id, parent=service.id),
                nocache=deployment.ignore_build_cache,
                network_mode=build_network,
                container_limits={
                    "cpushares": 512,  # Relative CPU weight (1024 = full CPU, 512 = 50%)
                },
            )
            image_id = None
            _, build_output = itertools.tee(json_stream(build_output))
            for chunk in build_output:
                log: dict[str, Any] = chunk  # type: ignore
                if "error" in log:
                    log_lines = [
                        f"{Colors.RED}{line}{Colors.ENDC}"
                        for line in cast(str, log["error"].rstrip()).splitlines()
                    ]
                    await deployment_log(
                        deployment=details.deployment,
                        message=log_lines,
                        source=RuntimeLogSource.BUILD,
                        error=True,
                    )
                if "stream" in log:
                    log_lines = [
                        f"{Colors.BLUE}{line}{Colors.ENDC}"
                        for line in cast(str, log["stream"].rstrip()).splitlines()
                    ]
                    await deployment_log(
                        deployment=details.deployment,
                        message=log_lines,
                        source=RuntimeLogSource.BUILD,
                    )
                    match = re.search(
                        r"(^Successfully built |sha256:)([0-9a-f]+)$", log["stream"]
                    )
                    if match:
                        image_id = match.group(2)

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
            git_deployment.build_finished_at = timezone.now()
            await git_deployment.asave()

    @activity.defn
    async def cleanup_built_image(self, image_tag: str):
        try:
            image = self.docker_client.images.get(image_tag)
        except docker.errors.NotFound:
            pass
        else:
            image.remove(force=True)
