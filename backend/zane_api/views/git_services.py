import secrets
import time
from typing import cast
import django.db.transaction as transaction
from django.db import IntegrityError
from django.db.models import Q
from drf_spectacular.utils import (
    extend_schema,
    PolymorphicProxySerializer,
)
from faker import Faker
from rest_framework import status, exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.serializers import Serializer
from rest_framework.utils.serializer_helpers import ReturnDict

from git_connectors.dtos import GitCommitInfo
from ..dtos import (
    URLDto,
    ConfigDto,
    VolumeDto,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
)
from ..constants import HEAD_COMMIT

from .base import (
    ResourceConflict,
)

from .serializers import (
    GitServiceDeployRequestSerializer,
    GitServiceDockerfileBuilderRequestSerializer,
    GitServiceBuilderRequestSerializer,
    GitServiceNixpacksBuilderRequestSerializer,
    GitServiceRailpackBuilderRequestSerializer,
    GitServiceReDeployRequestSerializer,
    GitServiceStaticDirBuilderRequestSerializer,
)
from ..models import (
    Project,
    Service,
    DeploymentChange,
    Environment,
    Deployment,
    ArchivedProject,
    ArchivedGitService,
    URL,
    GitApp,
)
from ..serializers import (
    ServiceDeploymentSerializer,
    ServiceSerializer,
    ErrorResponse409Serializer,
    EnvironmentSerializer,
)

from temporal.client import TemporalClient
from temporal.shared import (
    CancelDeploymentSignalInput,
    DeploymentDetails,
    SimpleGitDeploymentDetails,
    ArchivedGitServiceDetails,
)
from temporal.workflows import (
    DeployGitServiceWorkflow,
    ArchiveGitServiceWorkflow,
)
from .helpers import diff_service_snapshots
from temporal.helpers import generate_caddyfile_for_static_website


class CreateGitServiceAPIView(APIView):
    serializer_class = ServiceSerializer

    @extend_schema(
        request=PolymorphicProxySerializer(
            component_name="CreateGitServiceRequest",
            serializers=[
                GitServiceDockerfileBuilderRequestSerializer,
                GitServiceStaticDirBuilderRequestSerializer,
                GitServiceNixpacksBuilderRequestSerializer,
                GitServiceRailpackBuilderRequestSerializer,
            ],
            resource_type_field_name="builder",
        ),
        responses={
            409: ErrorResponse409Serializer,
            201: ServiceSerializer,
        },
        operation_id="createGitService",
        summary="Create a docker service",
        description="Create a service from a docker image.",
    )
    @transaction.atomic()
    def post(
        self,
        request: Request,
        project_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug, owner=request.user)

            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        else:
            builder_serializer_map = {
                Service.Builder.DOCKERFILE: GitServiceDockerfileBuilderRequestSerializer,
                Service.Builder.STATIC_DIR: GitServiceStaticDirBuilderRequestSerializer,
                Service.Builder.NIXPACKS: GitServiceNixpacksBuilderRequestSerializer,
                Service.Builder.RAILPACK: GitServiceRailpackBuilderRequestSerializer,
            }
            serializer = GitServiceBuilderRequestSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                data = cast(ReturnDict, serializer.validated_data)
                builder = data["builder"]
                form_serializer_class: type[Serializer] = builder_serializer_map[
                    builder
                ]
                form = form_serializer_class(data=request.data)

                if form.is_valid(raise_exception=True):
                    data = cast(ReturnDict, form.validated_data)

                    # Create service in DB
                    fake = Faker()
                    Faker.seed(time.monotonic())
                    service_slug = data.get("slug", fake.slug()).lower()
                    try:
                        service = Service.objects.create(
                            type=Service.ServiceType.GIT_REPOSITORY,
                            slug=service_slug,
                            project=project,
                            deploy_token=secrets.token_hex(16),
                            environment=environment,
                        )
                    except IntegrityError:
                        raise ResourceConflict(
                            detail=f"A service with the slug `{service_slug}` already exists in this environment."
                        )
                    else:
                        service.network_alias = (
                            f"zn-{service.slug}-{service.unprefixed_id}"
                        )

                        source_data = {
                            "repository_url": data["repository_url"],
                            "branch_name": data["branch_name"],
                            "commit_sha": HEAD_COMMIT,
                        }
                        if data.get("git_app_id") is not None:
                            gitapp = (
                                GitApp.objects.filter(id=data.get("git_app_id"))
                                .select_related("github", "gitlab")
                                .get()
                            )

                            source_data["git_app"] = dict(
                                id=gitapp.id,
                                github=(
                                    dict(
                                        id=gitapp.github.id,
                                        name=gitapp.github.name,
                                        installation_id=gitapp.github.installation_id,
                                        app_url=gitapp.github.app_url,
                                        app_id=gitapp.github.app_id,
                                    )
                                    if gitapp.github is not None
                                    else None
                                ),
                                gitlab=(
                                    dict(
                                        id=gitapp.gitlab.id,
                                        name=gitapp.gitlab.name,
                                        gitlab_url=gitapp.gitlab.gitlab_url,
                                        app_id=gitapp.gitlab.app_id,
                                    )
                                    if gitapp.gitlab is not None
                                    else None
                                ),
                            )

                        DeploymentChange.objects.create(
                            field=DeploymentChange.ChangeField.GIT_SOURCE,
                            new_value=source_data,
                            type=DeploymentChange.ChangeType.UPDATE,
                            service=service,
                        )

                        match builder:
                            case Service.Builder.DOCKERFILE:
                                builder_options = {
                                    "dockerfile_path": data["dockerfile_path"],
                                    "build_context_dir": data["build_context_dir"],
                                    "build_stage_target": None,
                                }
                            case Service.Builder.STATIC_DIR:
                                builder_options = {
                                    "publish_directory": data["publish_directory"],
                                    "is_spa": data["is_spa"],
                                    "not_found_page": data.get("not_found_page"),
                                    "index_page": data["index_page"],
                                }
                                builder_options["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        StaticDirectoryBuilderOptions.from_dict(
                                            builder_options
                                        )
                                    )
                                )
                                DeploymentChange.objects.create(
                                    field=DeploymentChange.ChangeField.URLS,
                                    new_value={
                                        "domain": URL.generate_default_domain(service),
                                        "base_path": "/",
                                        "strip_prefix": True,
                                        "associated_port": 80,
                                    },
                                    type=DeploymentChange.ChangeType.ADD,
                                    service=service,
                                )
                            case Service.Builder.NIXPACKS | Service.Builder.RAILPACK:
                                builder_options = {
                                    "build_directory": data["build_directory"],
                                    "custom_install_command": None,
                                    "custom_build_command": None,
                                    "custom_start_command": None,
                                    # Static options
                                    "is_static": data["is_static"],
                                    "publish_directory": data["publish_directory"],
                                    "is_spa": data["is_spa"],
                                    "not_found_page": "./404.html",
                                    "index_page": None,
                                }
                                builder_options["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        NixpacksBuilderOptions.from_dict(
                                            builder_options
                                        )
                                    )
                                    if data["is_static"]
                                    else None
                                )
                                extra_changes = [
                                    DeploymentChange(
                                        field=DeploymentChange.ChangeField.URLS,
                                        new_value={
                                            "domain": URL.generate_default_domain(
                                                service
                                            ),
                                            "base_path": "/",
                                            "strip_prefix": True,
                                            "associated_port": (
                                                80
                                                if data["is_static"]
                                                else data["exposed_port"]
                                            ),
                                        },
                                        type=DeploymentChange.ChangeType.ADD,
                                        service=service,
                                    ),
                                ]
                                if not data["is_static"]:
                                    extra_changes.append(
                                        DeploymentChange(
                                            field=DeploymentChange.ChangeField.ENV_VARIABLES,
                                            new_value={
                                                "key": "PORT",
                                                "value": str(data["exposed_port"]),
                                            },
                                            type=DeploymentChange.ChangeType.ADD,
                                            service=service,
                                        ),
                                    )
                                    extra_changes.append(
                                        DeploymentChange(
                                            field=DeploymentChange.ChangeField.ENV_VARIABLES,
                                            new_value={
                                                "key": "HOST",
                                                "value": "0.0.0.0",
                                            },
                                            type=DeploymentChange.ChangeType.ADD,
                                            service=service,
                                        ),
                                    )
                                DeploymentChange.objects.bulk_create(extra_changes)

                            case _:
                                raise NotImplementedError(
                                    f"This builder `{builder}` type has not yet been implemented"
                                )

                        builder_data = {
                            "builder": builder,
                            "options": builder_options,
                        }
                        DeploymentChange.objects.create(
                            field=DeploymentChange.ChangeField.BUILDER,
                            new_value=builder_data,
                            type=DeploymentChange.ChangeType.UPDATE,
                            service=service,
                        )

                        service.save()

                    response = ServiceSerializer(service)
                    return Response(response.data, status=status.HTTP_201_CREATED)


class DeployGitServiceAPIView(APIView):
    serializer_class = ServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=GitServiceDeployRequestSerializer,
        operation_id="deployGitService",
        summary="Deploy a git service",
        description="Apply all pending changes for the service and trigger a new deployment.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = (
                Service.objects.filter(
                    Q(slug=service_slug)
                    & Q(project=project)
                    & Q(environment=environment)
                    & Q(type=Service.ServiceType.GIT_REPOSITORY)
                )
                .select_related(
                    "project",
                    "healthcheck",
                    "environment",
                    "git_app",
                    "git_app__github",
                    "git_app__gitlab",
                )
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes", "configs"
                )
            ).get()
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A git service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        form = GitServiceDeployRequestSerializer(data=request.data or {})
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)
        deployments_to_cancel = []
        if data.get("cleanup_queue"):
            deployments_to_cancel = Deployment.flag_deployments_for_cancellation(
                service, include_running_deployments=True
            )

        new_deployment = service.prepare_new_git_deployment(
            ignore_build_cache=data["ignore_build_cache"]
        )

        payload = DeploymentDetails.from_deployment(deployment=new_deployment)

        def commit_callback():
            for dpl in deployments_to_cancel:
                TemporalClient.workflow_signal(
                    workflow=DeployGitServiceWorkflow.run,  # type: ignore
                    input=CancelDeploymentSignalInput(deployment_hash=dpl.hash),
                    signal=DeployGitServiceWorkflow.cancel_deployment,  # type: ignore
                    workflow_id=dpl.workflow_id,
                )
            TemporalClient.start_workflow(
                workflow=DeployGitServiceWorkflow.run,
                arg=payload,
                id=payload.workflow_id,
            )

        transaction.on_commit(commit_callback)

        response = ServiceDeploymentSerializer(new_deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class ReDeployGitServiceAPIView(APIView):
    serializer_class = ServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=GitServiceReDeployRequestSerializer,
        operation_id="reDeployGitService",
        summary="Redeploy a git service",
        description="Revert the service to the state of a previous deployment.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = (
                Service.objects.filter(
                    Q(slug=service_slug)
                    & Q(project=project)
                    & Q(environment=environment)
                    & Q(type=Service.ServiceType.GIT_REPOSITORY)
                )
                .select_related("project", "healthcheck", "environment")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes", "configs"
                )
            ).get()
            deployment = service.deployments.get(hash=deployment_hash)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A git service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

        form = GitServiceReDeployRequestSerializer(data=request.data or {})
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        latest_deployment: Deployment = service.latest_production_deployment  # type: ignore

        if latest_deployment.service_snapshot.get("environment") is None:  # type: ignore
            latest_deployment.service_snapshot["environment"] = dict(EnvironmentSerializer(environment).data)  # type: ignore
        if deployment.service_snapshot.get("environment") is None:  # type: ignore
            deployment.service_snapshot["environment"] = dict(EnvironmentSerializer(environment).data)  # type: ignore

        if latest_deployment.service_snapshot.get("global_network_alias") is None:  # type: ignore
            latest_deployment.service_snapshot["global_network_alias"] = service.global_network_alias  # type: ignore
        if deployment.service_snapshot.get("global_network_alias") is None:  # type: ignore
            deployment.service_snapshot["global_network_alias"] = service.global_network_alias  # type: ignore

        current_snapshot = (
            latest_deployment.service_snapshot
            if latest_deployment.status != Deployment.DeploymentStatus.FAILED
            else cast(ReturnDict, ServiceSerializer(service).data)
        )
        changes = diff_service_snapshots(
            current_snapshot,  # type: ignore
            deployment.service_snapshot,  # type: ignore
        )

        for change in changes:
            service.add_change(change)

        new_deployment = service.prepare_new_git_deployment(
            ignore_build_cache=data["ignore_build_cache"],
            is_redeploy_of=deployment,
            commit=GitCommitInfo(
                sha=cast(str, deployment.commit_sha),
                message=deployment.commit_message,
                author_name=deployment.commit_author_name,
            ),
        )

        payload = DeploymentDetails.from_deployment(deployment=new_deployment)

        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                workflow=DeployGitServiceWorkflow.run,
                arg=payload,
                id=payload.workflow_id,
            )
        )

        response = ServiceDeploymentSerializer(new_deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class ArchiveGitServiceAPIView(APIView):
    @extend_schema(
        responses={
            204: None,
        },
        operation_id="archiveGitService",
        summary="Archive a git service",
        description="Archive a git service.",
    )
    @transaction.atomic()
    def delete(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = (
                Service.objects.filter(
                    Q(slug=service_slug)
                    & Q(project=project)
                    & Q(environment=environment)
                    & Q(type=Service.ServiceType.GIT_REPOSITORY)
                )
                .select_related("project", "healthcheck", "environment")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes", "configs"
                )
            ).get()
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A git service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        if service.preview_environments.exists():
            raise exceptions.PermissionDenied(
                "Cannot delete a service that is attached to a preview environment, delete related preview environments before deleting this service."
            )

        if service.deployments.count() > 0:  # type: ignore
            archived_project: ArchivedProject | None = (
                project.archived_version  # type: ignore
                if hasattr(project, "archived_version")
                else None
            )
            if archived_project is None:
                archived_project = ArchivedProject.create_from_project(project)

            archived_service = ArchivedGitService.create_from_service(
                service, archived_project
            )

            payload = ArchivedGitServiceDetails(
                original_id=archived_service.original_id,
                urls=[
                    URLDto(
                        domain=url.domain,
                        base_path=url.base_path,
                        strip_prefix=url.strip_prefix,
                        id=url.original_id,
                    )
                    for url in archived_service.urls.all()
                ],
                volumes=[
                    VolumeDto(
                        container_path=volume.container_path,
                        mode=volume.mode,
                        name=volume.name,
                        host_path=volume.host_path,
                        id=volume.original_id,
                    )
                    for volume in archived_service.volumes.all()
                ],
                configs=[
                    ConfigDto(
                        mount_path=config.mount_path,
                        name=config.name,
                        id=config.original_id,
                        language=config.language,
                        contents=config.contents,
                    )
                    for config in archived_service.configs.all()
                ],
                project_id=archived_project.original_id,
                deployments=[
                    SimpleGitDeploymentDetails(
                        hash=dpl["hash"],  # type: ignore
                        urls=dpl["urls"],  # type: ignore
                        commit_sha=dpl["commit_sha"],
                        image_tag=dpl["image_tag"],
                        project_id=archived_service.project.original_id,
                        service_id=archived_service.original_id,
                    )
                    for dpl in archived_service.deployments
                ],
            )

            transaction.on_commit(
                lambda: TemporalClient.start_workflow(
                    workflow=ArchiveGitServiceWorkflow.run,
                    arg=payload,
                    id=archived_service.workflow_id,
                )
            )

        service.delete_resources()
        service.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
