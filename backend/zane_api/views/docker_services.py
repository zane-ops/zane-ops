import secrets
import time
from typing import Any, Dict, List, Optional, cast

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
from rest_framework.serializers import Serializer
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView

from .base import ResourceConflict
from .helpers import (
    compute_snapshot_excluding_change,
    diff_service_snapshots,
)
from .serializers import (
    BulkToggleServiceStateRequestSerializer,
    ConfigItemChangeSerializer,
    DockerServiceCreateRequestSerializer,
    DockerSourceFieldChangeSerializer,
    EnvStringChangeSerializer,
    GitBuilderFieldChangeSerializer,
    GitSourceFieldChangeSerializer,
    ToggleServiceStateRequestSerializer,
    VolumeItemChangeSerializer,
    DockerCommandFieldChangeSerializer,
    URLItemChangeSerializer,
    EnvItemChangeSerializer,
    PortItemChangeSerializer,
    HealthcheckFieldChangeSerializer,
    DockerDeploymentFieldChangeRequestSerializer,
    DockerServiceDeployRequestSerializer,
    ResourceLimitChangeSerializer,
    SharedVolumeItemChangeSerializer,
)
from ..dtos import (
    ConfigDto,
    URLDto,
    VolumeDto,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
)
from ..models import (
    Project,
    Service,
    Deployment,
    ArchivedProject,
    ArchivedDockerService,
    DeploymentChange,
    Environment,
    GitApp,
)
from ..serializers import (
    ConfigSerializer,
    ServiceDeploymentSerializer,
    ServiceSerializer,
    HealthCheckSerializer,
    VolumeSerializer,
    URLModelSerializer,
    PortConfigurationSerializer,
    EnvVariableSerializer,
    ErrorResponse409Serializer,
    EnvironmentSerializer,
    SharedVolumeSerializer,
)
from temporal.client import TemporalClient
from temporal.shared import (
    CancelDeploymentSignalInput,
    DeploymentDetails,
    ArchivedDockerServiceDetails,
    SimpleDeploymentDetails,
    ToggleServiceDetails,
)
from temporal.helpers import generate_caddyfile_for_static_website
from temporal.workflows import (
    DeployDockerServiceWorkflow,
    ToggleDockerServiceWorkflow,
    ArchiveDockerServiceWorkflow,
)
from rest_framework.utils.serializer_helpers import ReturnDict
from io import StringIO

from dotenv import dotenv_values
from container_registry.models import SharedRegistryCredentials


class CreateDockerServiceAPIView(APIView):
    serializer_class = ServiceSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            201: ServiceSerializer,
        },
        operation_id="createDockerService",
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
            form = DockerServiceCreateRequestSerializer(data=request.data)
            if form.is_valid(raise_exception=True):
                data = cast(ReturnDict, form.data)

                # Create service in DB
                container_registry_credentials_id: Optional[str] = data.get(
                    "container_registry_credentials_id"
                )
                container_registry_credentials: Optional[SharedRegistryCredentials] = (
                    None
                )
                if container_registry_credentials_id is not None:
                    container_registry_credentials = (
                        SharedRegistryCredentials.objects.get(
                            pk=container_registry_credentials_id
                        )
                    )

                fake = Faker()
                Faker.seed(time.monotonic())
                service_slug = data.get("slug", fake.slug()).lower()
                try:
                    service = Service.objects.create(
                        slug=service_slug,
                        project=project,
                        deploy_token=secrets.token_hex(16),
                        environment=environment,
                    )

                    service.network_alias = Service.generate_network_alias(service)

                    source_data = {
                        "image": data["image"],  # type: ignore
                    }

                    if container_registry_credentials is not None:
                        source_data["container_registry_credentials"] = dict(
                            id=container_registry_credentials.id,
                            url=container_registry_credentials.url,
                            registry_type=container_registry_credentials.registry_type,
                            username=container_registry_credentials.username,
                            password=container_registry_credentials.password,
                        )

                    DeploymentChange.objects.create(
                        field=DeploymentChange.ChangeField.SOURCE,
                        new_value=source_data,
                        type=DeploymentChange.ChangeType.UPDATE,
                        service=service,
                    )

                    service.save()
                except IntegrityError:
                    raise ResourceConflict(
                        detail=f"A service with the slug `{service_slug}` already exists in this environment."
                    )

                response = ServiceSerializer(service)
                return Response(response.data, status=status.HTTP_201_CREATED)


class RequestServiceChangesAPIView(APIView):
    serializer_class = ServiceSerializer

    @extend_schema(
        request=PolymorphicProxySerializer(
            component_name="DeploymentChangeRequest",
            serializers=[
                URLItemChangeSerializer,
                VolumeItemChangeSerializer,
                SharedVolumeItemChangeSerializer,
                EnvItemChangeSerializer,
                PortItemChangeSerializer,
                DockerSourceFieldChangeSerializer,
                DockerCommandFieldChangeSerializer,
                HealthcheckFieldChangeSerializer,
                ResourceLimitChangeSerializer,
                ConfigItemChangeSerializer,
                GitSourceFieldChangeSerializer,
                GitBuilderFieldChangeSerializer,
            ],
            resource_type_field_name="field",
        ),
        responses={
            200: ServiceSerializer,
        },
        operation_id="requestServiceChanges",
        summary="Request config changes",
        description="Request a change to the configuration of a service.",
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
                )
                .select_related(
                    "project",
                    "healthcheck",
                    "environment",
                    "container_registry_credentials",
                    "git_app",
                    "git_app__github",
                    "git_app__gitlab",
                )
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes"
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
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        field_serializer_map = {
            DeploymentChange.ChangeField.URLS: URLItemChangeSerializer,
            DeploymentChange.ChangeField.VOLUMES: VolumeItemChangeSerializer,
            DeploymentChange.ChangeField.ENV_VARIABLES: EnvItemChangeSerializer,
            DeploymentChange.ChangeField.PORTS: PortItemChangeSerializer,
            DeploymentChange.ChangeField.COMMAND: DockerCommandFieldChangeSerializer,
            DeploymentChange.ChangeField.SOURCE: DockerSourceFieldChangeSerializer,
            DeploymentChange.ChangeField.GIT_SOURCE: GitSourceFieldChangeSerializer,
            DeploymentChange.ChangeField.BUILDER: GitBuilderFieldChangeSerializer,
            DeploymentChange.ChangeField.HEALTHCHECK: HealthcheckFieldChangeSerializer,
            DeploymentChange.ChangeField.RESOURCE_LIMITS: ResourceLimitChangeSerializer,
            DeploymentChange.ChangeField.CONFIGS: ConfigItemChangeSerializer,
            DeploymentChange.ChangeField.SHARED_VOLUMES: SharedVolumeItemChangeSerializer,
        }

        request_serializer = DockerDeploymentFieldChangeRequestSerializer(
            data=request.data
        )
        if request_serializer.is_valid(raise_exception=True):
            form_serializer_class: type[Serializer] = field_serializer_map[
                cast(ReturnDict, request_serializer.data)["field"]
            ]
            form = form_serializer_class(
                data=request.data, context={"service": service}
            )
            if form.is_valid(raise_exception=True):
                data = cast(ReturnDict, form.data)
                field = data["field"]
                new_value: dict | None = data.get("new_value")
                item_id = data.get("item_id")
                change_type = data.get("type")
                old_value: Any = None
                match field:
                    case DeploymentChange.ChangeField.COMMAND:
                        old_value = getattr(service, field)
                    case DeploymentChange.ChangeField.RESOURCE_LIMITS:
                        if new_value is not None and len(new_value) == 0:
                            new_value = None
                        old_value = getattr(service, field)
                    case DeploymentChange.ChangeField.SOURCE:
                        new_value = cast(dict, new_value)
                        if service.type == Service.ServiceType.DOCKER_REGISTRY:
                            container_registry_credentials_id: Optional[str] = (
                                new_value.get("container_registry_credentials_id")
                            )
                            container_registry_credentials: Optional[
                                SharedRegistryCredentials
                            ] = None

                            if container_registry_credentials_id is not None:
                                container_registry_credentials = (
                                    SharedRegistryCredentials.objects.get(
                                        pk=container_registry_credentials_id
                                    )
                                )
                                new_value["container_registry_credentials"] = dict(
                                    id=container_registry_credentials.id,
                                    url=container_registry_credentials.url,
                                    registry_type=container_registry_credentials.registry_type,
                                    username=container_registry_credentials.username,
                                    password=container_registry_credentials.password,
                                )
                                # remove unused id
                                new_value.pop("container_registry_credentials_id", None)
                            old_value = {
                                "image": service.image,
                                "credentials": service.credentials,  # for backwards compatibility
                                "container_registry_credentials": dict(
                                    id=service.container_registry_credentials.id,
                                    url=service.container_registry_credentials.url,
                                    registry_type=service.container_registry_credentials.registry_type,
                                    username=service.container_registry_credentials.username,
                                    password=service.container_registry_credentials.password,
                                )
                                if service.container_registry_credentials is not None
                                else None,
                            }
                        else:
                            # prevent adding the change for git services
                            new_value = old_value
                    case DeploymentChange.ChangeField.GIT_SOURCE:
                        if service.type == Service.ServiceType.GIT_REPOSITORY:
                            if service.repository_url is not None:
                                gitapp = service.git_app
                                old_value = dict(
                                    repository_url=service.repository_url,
                                    branch_name=service.branch_name,
                                    commit_sha=service.commit_sha,
                                    git_app=(
                                        dict(
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
                                        if gitapp is not None
                                        else None
                                    ),
                                )

                            if new_value is not None:
                                if new_value.get("git_app_id") is not None:
                                    new_value = cast(dict, new_value)
                                    gitapp = (
                                        GitApp.objects.filter(
                                            id=new_value.get("git_app_id")
                                        )
                                        .select_related("github", "gitlab")
                                        .get()
                                    )

                                    new_value["git_app"] = dict(
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

                                new_value.pop("git_app_id", None)

                        else:
                            # prevent adding the change for docker services
                            new_value = old_value
                    case DeploymentChange.ChangeField.BUILDER:
                        if service.type == Service.ServiceType.GIT_REPOSITORY:
                            if service.builder is not None:
                                old_value = {
                                    "builder": service.builder,
                                }
                                match service.builder:
                                    case Service.Builder.DOCKERFILE:
                                        old_value["options"] = (
                                            service.dockerfile_builder_options
                                        )
                                    case Service.Builder.STATIC_DIR:
                                        old_value["options"] = (
                                            service.static_dir_builder_options
                                        )
                                    case Service.Builder.NIXPACKS:
                                        old_value["options"] = (
                                            service.nixpacks_builder_options
                                        )
                                    case Service.Builder.RAILPACK:
                                        old_value["options"] = (
                                            service.railpack_builder_options
                                        )
                                    case _:
                                        raise NotImplementedError(
                                            f"This builder `{service.builder}` is not supported yet"
                                        )

                            new_value = cast(Dict[str, Any], new_value)
                            new_builder = new_value["builder"]
                            match new_builder:
                                case Service.Builder.DOCKERFILE:
                                    new_value = {
                                        "builder": Service.Builder.DOCKERFILE,
                                        "options": {
                                            "build_context_dir": new_value[
                                                "build_context_dir"
                                            ],
                                            "dockerfile_path": new_value[
                                                "dockerfile_path"
                                            ],
                                            "build_stage_target": new_value[
                                                "build_stage_target"
                                            ],
                                        },
                                    }
                                case Service.Builder.STATIC_DIR:
                                    new_value = {
                                        "builder": Service.Builder.STATIC_DIR,
                                        "options": {
                                            "publish_directory": new_value[
                                                "publish_directory"
                                            ],
                                            "is_spa": new_value["is_spa"],
                                            "not_found_page": new_value.get(
                                                "not_found_page"
                                            ),
                                            "index_page": new_value["index_page"],
                                        },
                                    }

                                    new_value["options"]["generated_caddyfile"] = (
                                        generate_caddyfile_for_static_website(
                                            StaticDirectoryBuilderOptions.from_dict(
                                                new_value["options"]
                                            )
                                        )
                                    )
                                case (
                                    Service.Builder.NIXPACKS | Service.Builder.RAILPACK
                                ):
                                    new_value = {
                                        "builder": new_value["builder"],
                                        "options": {
                                            "build_directory": new_value[
                                                "build_directory"
                                            ],
                                            "custom_install_command": new_value[
                                                "custom_install_command"
                                            ],
                                            "custom_build_command": new_value[
                                                "custom_build_command"
                                            ],
                                            "custom_start_command": new_value[
                                                "custom_start_command"
                                            ],
                                            # Static options
                                            "is_static": new_value["is_static"],
                                            "publish_directory": new_value[
                                                "publish_directory"
                                            ],
                                            "is_spa": new_value["is_spa"],
                                            "not_found_page": new_value.get(
                                                "not_found_page"
                                            ),
                                            "index_page": new_value["index_page"],
                                        },
                                    }

                                    new_value["options"]["generated_caddyfile"] = (
                                        generate_caddyfile_for_static_website(
                                            NixpacksBuilderOptions.from_dict(
                                                new_value["options"]
                                            )
                                        )
                                        if new_value["options"]["is_static"]
                                        else None
                                    )
                                case _:
                                    raise NotImplementedError(
                                        f"This builder `{new_builder}` is not supported yet"
                                    )
                        else:
                            # prevent adding the change for docker services
                            new_value = old_value
                    case DeploymentChange.ChangeField.HEALTHCHECK:
                        old_value = (
                            HealthCheckSerializer(service.healthcheck).data
                            if service.healthcheck is not None
                            else None
                        )
                    case DeploymentChange.ChangeField.VOLUMES:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = VolumeSerializer(
                                service.volumes.get(id=item_id)
                            ).data
                    case DeploymentChange.ChangeField.VOLUMES:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = SharedVolumeSerializer(
                                service.shared_volumes.filter(id=item_id)
                                .select_related("volume", "volume__service")
                                .get()
                            ).data
                    case DeploymentChange.ChangeField.CONFIGS:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = ConfigSerializer(
                                service.configs.get(id=item_id)
                            ).data
                    case DeploymentChange.ChangeField.URLS:
                        old_value = None
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = URLModelSerializer(
                                service.urls.get(id=item_id)
                            ).data
                    case DeploymentChange.ChangeField.PORTS:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = PortConfigurationSerializer(
                                service.ports.get(id=item_id)
                            ).data
                    case DeploymentChange.ChangeField.ENV_VARIABLES:
                        if change_type in ["UPDATE", "DELETE"]:
                            old_value = EnvVariableSerializer(
                                service.env_variables.get(id=item_id)  # type: ignore
                            ).data

                if new_value != old_value:
                    service.add_change(
                        DeploymentChange(
                            type=change_type,
                            field=field,
                            old_value=old_value,
                            new_value=new_value,
                            service=service,
                            item_id=item_id,
                        )
                    )

                response = ServiceSerializer(service)
                return Response(response.data, status=status.HTTP_200_OK)


class RequestServiceEnvChangesAPIView(APIView):
    serializer_class = ServiceSerializer

    @extend_schema(
        request=EnvStringChangeSerializer,
        operation_id="requestEnvChanges",
        summary="Request env changes",
        description="Request a change to the environments variables of a service.",
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
                )
                .select_related(
                    "project",
                    "healthcheck",
                    "container_registry_credentials",
                )
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes"
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
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        form = EnvStringChangeSerializer(
            data=request.data, context={"service": service}
        )
        if form.is_valid(raise_exception=True):
            data = form.data
            new_value = data.get("new_value")  # type: ignore

            values = dotenv_values(stream=StringIO(new_value))

            for key, value in values.items():
                service.add_change(
                    DeploymentChange(
                        type=DeploymentChange.ChangeType.ADD,
                        field=DeploymentChange.ChangeField.ENV_VARIABLES,
                        new_value={
                            "key": key,
                            "value": value,
                        },
                        service=service,
                    )
                )

            response = ServiceSerializer(service)
            return Response(response.data, status=status.HTTP_200_OK)


class CancelServiceChangesAPIView(APIView):
    @extend_schema(
        responses={
            409: ErrorResponse409Serializer,
            204: None,
        },
        operation_id="cancelServiceChanges",
        summary="Cancel a config change",
        description="Cancel a config change that was requested.",
    )
    def delete(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        change_id: str,
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
                )
                .select_related(
                    "project",
                    "healthcheck",
                    "container_registry_credentials",
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
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        try:
            found_change = service.unapplied_changes.get(id=change_id)
        except DeploymentChange.DoesNotExist:
            raise exceptions.NotFound(
                f"A pending change with id `{change_id}` does not exist in this service."
            )
        else:
            snapshot = compute_snapshot_excluding_change(service, change_id=change_id)
            if (
                service.type == Service.ServiceType.DOCKER_REGISTRY
                and snapshot.image is None
            ):
                raise ResourceConflict(
                    detail="Cannot revert this change because it would remove the image of the service."
                )
            if service.type == Service.ServiceType.GIT_REPOSITORY:
                if snapshot.repository_url is None:
                    raise ResourceConflict(
                        detail="Cannot revert this change because it would remove the repository of the service."
                    )
                if snapshot.builder is None:
                    raise ResourceConflict(
                        detail="Cannot revert this change because it would remove the builder of the service."
                    )

            if snapshot.has_duplicate_volumes():
                raise ResourceConflict(
                    detail="Cannot revert this change as it would cause duplicate volumes with the same host path or container path for this service."
                )

            if snapshot.has_duplicate_configs():
                raise ResourceConflict(
                    detail="Cannot revert this change as it would cause duplicate config files with the same mounth path for this service."
                )

            found_change.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class DeployDockerServiceAPIView(APIView):
    serializer_class = ServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=DockerServiceDeployRequestSerializer,
        operation_id="deployDockerService",
        summary="Deploy a docker service",
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
                    & Q(type=Service.ServiceType.DOCKER_REGISTRY)
                )
                .select_related(
                    "project",
                    "healthcheck",
                    "environment",
                    "container_registry_credentials",
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
            exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        else:
            form = DockerServiceDeployRequestSerializer(
                data=request.data if request.data is not None else {}
            )
            if form.is_valid(raise_exception=True):
                data = cast(ReturnDict, form.data)
                commit_message = data.get("commit_message")

                deployments_to_cancel = []
                if data.get("cleanup_queue"):
                    deployments_to_cancel = (
                        Deployment.flag_deployments_for_cancellation(
                            service, include_running_deployments=True
                        )
                    )

                new_deployment = service.prepare_new_docker_deployment(
                    commit_message=commit_message
                )

                payload = DeploymentDetails.from_deployment(
                    deployment=new_deployment,
                )

                def commit_callback():
                    for dpl in deployments_to_cancel:
                        TemporalClient.workflow_signal(
                            workflow=(DeployDockerServiceWorkflow.run),  # type: ignore
                            input=CancelDeploymentSignalInput(deployment_hash=dpl.hash),
                            signal=(DeployDockerServiceWorkflow.cancel_deployment),  # type: ignore
                            workflow_id=dpl.workflow_id,
                        )

                    TemporalClient.start_workflow(
                        workflow=DeployDockerServiceWorkflow.run,
                        arg=payload,
                        id=payload.workflow_id,
                    )

                transaction.on_commit(commit_callback)

                response = ServiceDeploymentSerializer(new_deployment)
                return Response(response.data, status=status.HTTP_200_OK)


class RedeployDockerServiceAPIView(APIView):
    serializer_class = ServiceDeploymentSerializer

    @transaction.atomic()
    @extend_schema(
        request=None,
        operation_id="redeployDockerService",
        summary="Redeploy a docker service",
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
                & Q(type=Service.ServiceType.DOCKER_REGISTRY)
            )
            .select_related(
                "project",
                "healthcheck",
                "environment",
                "container_registry_credentials",
            )
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "changes", "configs"
            )
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        try:
            deployment = service.deployments.get(hash=deployment_hash)
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

        latest_deployment = cast(Deployment, service.latest_production_deployment)

        if latest_deployment.service_snapshot.get("environment") is None:  # type: ignore
            latest_deployment.service_snapshot["environment"] = dict(  # type: ignore
                EnvironmentSerializer(environment).data
            )
        if deployment.service_snapshot.get("environment") is None:  # type: ignore
            deployment.service_snapshot["environment"] = dict(  # type: ignore
                EnvironmentSerializer(environment).data
            )

        if latest_deployment.service_snapshot.get("global_network_alias") is None:  # type: ignore
            latest_deployment.service_snapshot["global_network_alias"] = (  # type: ignore
                service.global_network_alias
            )
        if deployment.service_snapshot.get("global_network_alias") is None:  # type: ignore
            deployment.service_snapshot["global_network_alias"] = (  # type: ignore
                service.global_network_alias
            )

        if (
            latest_deployment.service_snapshot.get("container_registry_credentials")  # type: ignore
            is None
        ):
            latest_deployment.service_snapshot["container_registry_credentials"] = (  # type: ignore
                service.container_registry_credentials
            )
        if deployment.service_snapshot.get("container_registry_credentials") is None:  # type: ignore
            deployment.service_snapshot["container_registry_credentials"] = (  # type: ignore
                service.container_registry_credentials
            )

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

        new_deployment = service.prepare_new_docker_deployment(
            is_redeploy_of=deployment
        )

        payload = DeploymentDetails.from_deployment(new_deployment)

        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                DeployDockerServiceWorkflow.run,
                payload,
                id=payload.workflow_id,
            )
        )

        response = ServiceDeploymentSerializer(new_deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class ServiceDetailsAPIView(RetrieveUpdateAPIView):
    serializer_class = ServiceSerializer
    queryset = (
        Service.objects.all()
    )  # only for drf-spectacular, in practice we use `get_queryset()`
    http_method_names = ["patch", "get"]
    lookup_field = "slug"

    @extend_schema(
        operation_id="updateService",
        summary="Update a service",
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def perform_update(self, serializer: ServiceSerializer):
        data = cast(dict, serializer.validated_data)
        try:
            return super().perform_update(serializer)
        except IntegrityError:
            raise ResourceConflict(
                detail=f"The slug `{data.get('slug')}` is already used by another service."
            )

    @extend_schema(
        operation_id="getSingleService",
        summary="Get single service",
        description="See all the details of a service.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["slug"]
        env_slug = self.kwargs.get("env_slug", Environment.PRODUCTION_ENV_NAME)

        try:
            project = Project.objects.get(
                slug=project_slug.lower(), owner=self.request.user
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = (
                Service.objects.filter(
                    Q(slug=service_slug)
                    & Q(project=project)
                    & Q(environment=environment)
                )
                .select_related("project", "healthcheck", "environment")
                .prefetch_related("volumes", "ports", "urls", "env_variables")
            )
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
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        return service


class ArchiveDockerServiceAPIView(APIView):
    @extend_schema(
        responses={
            204: None,
        },
        operation_id="archiveService",
        summary="Archive a service",
        description="Archive a service.",
    )
    @transaction.atomic()
    def delete(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
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
                & Q(type=Service.ServiceType.DOCKER_REGISTRY)
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

            archived_service = ArchivedDockerService.create_from_service(
                service, archived_project
            )

            payload = ArchivedDockerServiceDetails(
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
                    SimpleDeploymentDetails(
                        hash=dpl.get("hash"),  # type: ignore
                        urls=dpl.get("urls"),  # type: ignore
                        project_id=archived_service.project.original_id,
                        service_id=archived_service.original_id,
                    )
                    for dpl in archived_service.deployments
                ],
            )

            transaction.on_commit(
                lambda: TemporalClient.start_workflow(
                    workflow=ArchiveDockerServiceWorkflow.run,
                    arg=payload,
                    id=archived_service.workflow_id,
                )
            )

        service.delete_resources()
        service.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ToggleServiceAPIView(APIView):
    @extend_schema(
        request=ToggleServiceStateRequestSerializer,
        operation_id="toggleService",
        responses={409: ErrorResponse409Serializer, 202: None},
        summary="Stop/Restart a docker service",
        description="Stops a running docker service and restart it if it was stopped.",
    )
    @transaction.atomic()
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
                Q(slug=service_slug) & Q(project=project) & Q(environment=environment)
            ).select_related("project")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        form = ToggleServiceStateRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        production_deployment = service.latest_production_deployment
        if production_deployment is None:
            raise ResourceConflict(
                "This service has not been deployed yet, and thus its state cannot be toggled."
            )

        if production_deployment.service_snapshot.get("environment") is None:  # type: ignore
            production_deployment.service_snapshot["environment"] = dict(  # type: ignore
                EnvironmentSerializer(environment).data
            )
        if production_deployment.service_snapshot.get("global_network_alias") is None:  # type: ignore
            production_deployment.service_snapshot["global_network_alias"] = (  # type: ignore
                service.global_network_alias
            )

        payload = ToggleServiceDetails(
            desired_state=data["desired_state"],
            deployment=SimpleDeploymentDetails(
                hash=production_deployment.hash,
                project_id=project.id,
                service_id=service.id,
                status=production_deployment.status,
                service_snapshot=production_deployment.service_snapshot,
            ),
        )
        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                workflow=ToggleDockerServiceWorkflow.run,
                arg=payload,
                id=f"toggle-{service.id}-{project.id}",
            )
        )

        return Response(None, status=status.HTTP_202_ACCEPTED)


class BulkToggleServicesAPIView(APIView):
    @extend_schema(
        request=BulkToggleServiceStateRequestSerializer,
        operation_id="bulkToggleServices",
        responses={202: None},
        summary="Stop/Restart multiple services",
        description="Stops a running docker service and restart it if it was stopped.",
    )
    @transaction.atomic()
    def put(
        self,
        request: Request,
        project_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV_NAME,
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

        form = BulkToggleServiceStateRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        services = Service.objects.filter(
            Q(project=project)
            & Q(environment=environment)
            & Q(id__in=data["service_ids"])
        ).select_related("project")

        payloads: List[ToggleServiceDetails] = []
        for service in services:
            production_deployment = service.latest_production_deployment
            if production_deployment is None:
                continue

            if production_deployment.service_snapshot.get("environment") is None:  # type: ignore
                production_deployment.service_snapshot["environment"] = dict(  # type: ignore
                    EnvironmentSerializer(environment).data
                )

            if (
                production_deployment.service_snapshot.get("global_network_alias")  # type: ignore
                is None
            ):
                production_deployment.service_snapshot["global_network_alias"] = (  # type: ignore
                    service.global_network_alias
                )

            payloads.append(
                ToggleServiceDetails(
                    desired_state=data["desired_state"],
                    deployment=SimpleDeploymentDetails(
                        hash=production_deployment.hash,
                        project_id=project.id,
                        service_id=service.id,
                        status=production_deployment.status,
                        service_snapshot=production_deployment.service_snapshot,
                    ),
                )
            )
        if len(payloads) > 0:

            def commit_callback():
                for payload in payloads:
                    TemporalClient.start_workflow(
                        workflow=ToggleDockerServiceWorkflow.run,
                        arg=payload,
                        id=f"toggle-{payload.deployment.service_id}-{payload.deployment.project_id}",
                    )

            transaction.on_commit(commit_callback)
        return Response(None, status=status.HTTP_202_ACCEPTED)
