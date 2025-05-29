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

from ..git_client import GitClient
from ..dtos import (
    URLDto,
    ConfigDto,
    VolumeDto,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
)


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
    DeploymentURL,
    ArchivedProject,
    ArchivedGitService,
    URL,
)
from ..serializers import (
    ServiceDeploymentSerializer,
    ServiceSerializer,
    ErrorResponse409Serializer,
)

from ..utils import generate_random_chars
from temporal.main import (
    start_workflow,
)
from temporal.shared import (
    DeploymentDetails,
    SimpleGitDeploymentDetails,
    ArchivedGitServiceDetails,
)
from temporal.workflows import (
    DeployGitServiceWorkflow,
    ArchiveGitServiceWorkflow,
)
from .helpers import compute_docker_changes_from_snapshots
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
        env_slug: str = Environment.PRODUCTION_ENV,
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
                            deploy_token=generate_random_chars(20),
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
                            "commit_sha": "HEAD",
                        }

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
        env_slug: str = Environment.PRODUCTION_ENV,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
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
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A git service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        form = GitServiceDeployRequestSerializer(data=request.data or {})
        if form.is_valid(raise_exception=True):
            new_deployment = Deployment.objects.create(
                service=service,
                commit_message="-",
                ignore_build_cache=cast(ReturnDict, form.data)["ignore_build_cache"],
            )
            service.apply_pending_changes(deployment=new_deployment)

            ports = (
                service.urls.filter(associated_port__isnull=False)
                .values_list("associated_port", flat=True)
                .distinct()
            )
            for port in ports:
                DeploymentURL.generate_for_deployment(
                    deployment=new_deployment,
                    service=service,
                    port=port,
                )

            latest_deployment = service.latest_production_deployment
            commit_sha = service.commit_sha
            if commit_sha == "HEAD":
                git_client = GitClient()
                commit_sha = git_client.resolve_commit_sha_for_branch(service.repository_url, service.branch_name) or "HEAD"  # type: ignore

            new_deployment.commit_sha = commit_sha
            new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
            new_deployment.service_snapshot = ServiceSerializer(service).data  # type: ignore
            new_deployment.save()

            payload = DeploymentDetails.from_deployment(deployment=new_deployment)

            transaction.on_commit(
                lambda: start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                )
            )

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
        env_slug: str = Environment.PRODUCTION_ENV,
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

        try:
            deployment = service.deployments.get(hash=deployment_hash)
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

        form = GitServiceReDeployRequestSerializer(data=request.data or {})
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        latest_deployment: Deployment = service.latest_production_deployment  # type: ignore

        current_snapshot = (
            latest_deployment.service_snapshot
            if latest_deployment.status != Deployment.DeploymentStatus.FAILED
            else cast(ReturnDict, ServiceSerializer(service).data)
        )
        changes = compute_docker_changes_from_snapshots(
            current_snapshot,  # type: ignore
            deployment.service_snapshot,  # type: ignore
        )

        for change in changes:
            if change.field == DeploymentChange.ChangeField.GIT_SOURCE:
                # override the commit sha with the commit sha of the deployment instead
                change.new_value["commit_sha"] = deployment.commit_sha  # type: ignore
            service.add_change(change)

        new_deployment = Deployment.objects.create(
            service=service,
            commit_message=deployment.commit_message,
            commit_sha=deployment.commit_sha,
            ignore_build_cache=data["ignore_build_cache"],
            is_redeploy_of=deployment,
        )
        service.apply_pending_changes(deployment=new_deployment)

        ports = (
            service.urls.filter(associated_port__isnull=False)
            .values_list("associated_port", flat=True)
            .distinct()
        )
        for port in ports:
            DeploymentURL.generate_for_deployment(
                deployment=new_deployment,
                service=service,
                port=port,
            )

        new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
        new_deployment.service_snapshot = ServiceSerializer(service).data  # type: ignore
        new_deployment.save()

        payload = DeploymentDetails.from_deployment(deployment=new_deployment)

        transaction.on_commit(
            lambda: start_workflow(
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
        env_slug: str = Environment.PRODUCTION_ENV,
    ):
        project = (
            Project.objects.filter(
                slug=project_slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )

        environment = Environment.objects.filter(name=env_slug, project=project).first()
        if environment is None:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project."
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
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this environment."
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
                lambda: start_workflow(
                    workflow=ArchiveGitServiceWorkflow.run,
                    arg=payload,
                    id=archived_service.workflow_id,
                )
            )

        service.delete_resources()
        service.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
