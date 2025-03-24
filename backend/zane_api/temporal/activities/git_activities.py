import itertools
import re
from typing import Optional
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os

with workflow.unsafe.imports_passed_through():
    import docker.errors
    from ...models import (
        Project,
        ArchivedProject,
        ArchivedDockerService,
        Deployment,
        HealthCheck,
        URL,
        DeploymentChange,
        Service,
    )
    from docker.utils.json_stream import json_stream
    import shutil
    from ...git_client import GitClient, GitCloneFailedError, GitCheckoutFailedError
    from ..helpers import (
        deployment_log,
        get_docker_client,
        get_resource_labels,
        replace_env_variables,
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
        await deployment_log(
            deployment=details.deployment,
            message=f"Cloning repository to {Colors.ORANGE}{details.location}{Colors.ENDC}...",
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
                message=f"Failed cloning the repository to {Colors.ORANGE}{details.location}{Colors.ENDC} ❌: {Colors.GREY}{e}{Colors.ENDC}",
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
                    message=f"Failed checkout the repository at commit {Colors.ORANGE}{(deployment.commit_sha or 'HEAD')[:7]}{Colors.ENDC} ❌: {Colors.GREY}{e}{Colors.ENDC}",
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

        base_image = service.id.replace("_", "-")
        await deployment_log(
            deployment=deployment,
            message=f"Running {Colors.YELLOW}docker build -t {deployment.image_tag} -f {service.dockerfile_builder_options.dockerfile_path} {service.dockerfile_builder_options.build_context_dir} {Colors.ENDC}...",  # type: ignore
            source=RuntimeLogSource.BUILD,
        )
        try:
            context_dir = os.path.join(details.location, service.dockerfile_builder_options.build_context_dir)  # type: ignore
            dockerfile_path = os.path.join(details.location, service.dockerfile_builder_options.dockerfile_path)  # type: ignore

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

            build_output = self.docker_client.api.build(
                path=context_dir,
                dockerfile=dockerfile_path,
                tag=deployment.image_tag,
                buildargs=build_envs,
                # target="",
                rm=True,
                cache_from=[":".join([base_image, "latest"])],
                labels=get_resource_labels(service.project_id),
                nocache=deployment.ignore_build_cache,
            )
            image_id = None
            _, build_output = itertools.tee(json_stream(build_output))
            for chunk in build_output:
                log: dict = chunk  # type: ignore
                if "error" in log:
                    await deployment_log(
                        deployment=details.deployment,
                        message=f"{log['stream'].rstrip()}",
                        source=RuntimeLogSource.BUILD,
                        error=True,
                    )
                if "stream" in log:
                    await deployment_log(
                        deployment=details.deployment,
                        message=f"{Colors.BLUE}{log['stream'].rstrip()}{Colors.ENDC}",
                        source=RuntimeLogSource.BUILD,
                    )
                    match = re.search(
                        r"(^Successfully built |sha256:)([0-9a-f]+)$", log["stream"]
                    )
                    if match:
                        image_id = match.group(2)
                if "aux" in log and "ID" in log["aux"]:
                    image_id = log["aux"]["ID"]

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
