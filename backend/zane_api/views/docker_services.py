import time

import django_filters
import docker.errors
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, inline_serializer
from faker import Faker
from rest_framework import status, exceptions
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE, ResourceConflict
from .. import serializers
from ..docker_operations import (
    login_to_docker_registry,
    check_if_port_is_available_on_host,
    DOCKER_HUB_REGISTRY_URL,
    check_if_docker_image_exists,
)
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    Volume,
    PortConfiguration,
    URL,
    DockerEnvVariable,
    ArchivedProject,
    ArchivedDockerService,
    HealthCheck,
)
from ..tasks import deploy_docker_service, delete_resources_for_docker_service
from ..utils import strip_slash_if_exists
from ..validators import validate_url_path


class DockerCredentialsRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)
    registry_url = serializers.URLField(required=False, default=DOCKER_HUB_REGISTRY_URL)


class ServicePortsRequestSerializer(serializers.Serializer):
    public = serializers.IntegerField(required=False, default=80)
    forwarded = serializers.IntegerField(required=True)


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    mount_path = serializers.CharField(max_length=255)
    host_path = serializers.URLPathField(max_length=255, required=False)


class URLRequestSerializer(serializers.Serializer):
    domain = serializers.URLDomainField(required=True)
    base_path = serializers.URLPathField(required=False, default="/")
    strip_prefix = serializers.BooleanField(required=False, default=True)

    def validate(self, url: dict[str, str]):
        if url["domain"] == settings.ZANE_APP_DOMAIN:
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where zaneOps is installed is not allowed."
                    ]
                }
            )
        existing_urls = URL.objects.filter(
            domain=url["domain"].lower(), base_path=url["base_path"].lower()
        ).distinct()
        if len(existing_urls) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"""URL with domain `{url['domain']}` and base path `{url['base_path']}` """
                        f"is already assigned to another service."
                    ]
                }
            )

        domain = url["domain"]
        domain_parts = domain.split(".")
        domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)

        existing_parent_domain = URL.objects.filter(
            domain=domain_as_wildcard.lower()
        ).distinct()
        if len(existing_parent_domain) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{url['domain']}` can't be used because it will be shadowed by the wildcard"
                        f" domain `{domain_as_wildcard}` which is already assigned to another service."
                    ]
                }
            )

        return url


class HealthCheckRequestSerializer(serializers.Serializer):
    HEALTCHECK_CHOICES = (
        ("path", _("path")),
        ("command", _("command")),
    )
    type = serializers.CaseInsensitiveChoiceField(
        required=True, choices=HEALTCHECK_CHOICES
    )
    value = serializers.CharField(max_length=255, required=True)
    timeout_seconds = serializers.IntegerField(required=False, default=60, min_value=5)
    interval_seconds = serializers.CharField(required=False, default=30)

    def validate(self, data: dict):
        if data["type"] == "path":
            try:
                validate_url_path(data["value"])
            except ValidationError as e:
                raise serializers.ValidationError({"value": e.messages})
        return data


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    image = serializers.CharField(required=True)
    command = serializers.CharField(required=False)
    credentials = DockerCredentialsRequestSerializer(required=False)
    urls = URLRequestSerializer(many=True, required=False, default=[])
    ports = ServicePortsRequestSerializer(required=False, many=True, default=[])
    env = serializers.DictField(child=serializers.CharField(), required=False)
    volumes = VolumeRequestSerializer(many=True, required=False, default=[])
    healthcheck = HealthCheckRequestSerializer(required=False)

    def validate(self, data: dict):
        credentials = data.get("credentials")
        image = data.get("image")
        healthcheck = data.get("healthcheck")

        if credentials is not None:
            try:
                login_to_docker_registry(**dict(credentials))
            except docker.errors.APIError:
                raise serializers.ValidationError(
                    {"credentials": [f"Invalid credentials for the specified registry"]}
                )

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=dict(credentials) if credentials is not None else None,
        )
        if not do_image_exists:
            registry_url = (
                credentials.get("registry_url") if credentials is not None else None
            )
            if registry_url == DOCKER_HUB_REGISTRY_URL or registry_url is None:
                registry_str = "on Docker Hub"
            else:
                registry_str = f"in the specified registry"
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` does not exist `{registry_str}`"
                        f" or the credentials are invalid for this image."
                        f" Have you forgotten to include the credentials ?"
                    ]
                }
            )

        urls = data.get("urls", [])
        ports = data.get("ports", [])

        http_ports = [80, 443]
        if len(urls) > 0:
            for port in ports:
                if port["public"] not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "urls": [
                                f"Cannot specify both a custom URL and a public port other than a HTTP port (80/443)"
                            ]
                        }
                    )

        if healthcheck is not None and healthcheck["type"].lower() == "path":
            if len(ports) == 0 and len(urls) == 0:
                raise serializers.ValidationError(
                    {
                        "healthcheck": {
                            "path": [
                                f"healthcheck requires that at least one `url` or one `port` is provided"
                            ]
                        }
                    }
                )
        return data

    def validate_credentials(self, value: dict):
        try:
            login_to_docker_registry(
                username=value["username"],
                password=value["password"],
                registry_url=value.get("registry_url"),
            )
        except docker.errors.APIError:
            raise serializers.ValidationError("Invalid docker credentials")
        else:
            return value

    def validate_ports(self, ports: list[dict[str, int]]):
        no_of_http_ports = 0
        http_ports = [80, 443]
        public_ports_seen = set()
        for port in ports:
            public_port = port["public"]

            # Check for only 1 http port
            if public_port in http_ports:
                no_of_http_ports += 1
            if no_of_http_ports > 1:
                raise serializers.ValidationError("Only one HTTP port is allowed")

            # Check for duplicate public ports
            if public_port in public_ports_seen:
                raise serializers.ValidationError(
                    "Duplicate public port values are not allowed."
                )
            if public_port not in http_ports:
                public_ports_seen.add(public_port)

            # check if port is available
            if public_port not in http_ports:
                is_port_available = check_if_port_is_available_on_host(public_port)
                if not is_port_available:
                    raise serializers.ValidationError(
                        f"Port {public_port} is not available on the host machine."
                    )

        already_existing_ports = [
            str(port.host)
            for port in PortConfiguration.objects.filter(
                host__in=list(public_ports_seen)
            )
        ]

        if len(already_existing_ports) > 0:
            ports_str = ", ".join(already_existing_ports)

            if len(already_existing_ports) == 1:
                message = f"Port {ports_str} is already used by other services."
            else:
                message = f"Ports {ports_str} are already used by other services."
            raise serializers.ValidationError(message)

        return ports

    def validate_urls(self, value: list[dict[str, str]]):
        urls_seen = set()
        for url in value:
            new_url = (url["domain"], url["base_path"])
            if new_url in urls_seen:
                raise serializers.ValidationError(
                    "Duplicate urls values are not allowed."
                )
            urls_seen.add(new_url)
        return value

    def validate_volumes(self, value: list[dict[str, str]]):
        mount_paths_seen = set()
        for volume in value:
            mount_path = volume["mount_path"]
            if mount_path in mount_paths_seen:
                raise serializers.ValidationError(
                    "Cannot specify the same mount_path twice or more."
                )
            mount_paths_seen.add(mount_path)
        return value


class DockerServiceResponseSerializer(serializers.Serializer):
    service = serializers.DockerServiceSerializer(read_only=True)


class CreateDockerServiceAPIView(APIView):
    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            409: serializers.ErrorResponse409Serializer,
            201: DockerServiceResponseSerializer,
        },
        operation_id="createDockerService",
    )
    @transaction.atomic()
    def post(self, request: Request, project_slug: str):
        try:
            project = Project.objects.get(slug=project_slug, owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                f"A project with the slug `{project_slug}` does not exist"
            )
        else:
            form = DockerServiceCreateRequestSerializer(data=request.data)
            if form.is_valid(raise_exception=True):
                data = form.data

                # Create service in DB
                docker_credentials: dict | None = data.get("credentials")
                fake = Faker()
                Faker.seed(time.monotonic())
                service_slug = data.get("slug", fake.slug()).lower()
                docker_image_tag = "latest"
                try:
                    docker_image = data["image"]
                    docker_image_parts = docker_image.split(":", 1)
                    if len(docker_image_parts) == 2:
                        docker_image, docker_image_tag = docker_image_parts

                    healthcheck = data.get("healthcheck")
                    service = DockerRegistryService.objects.create(
                        slug=service_slug,
                        project=project,
                        image_repository=docker_image,
                        command=data.get("command"),
                        docker_credentials_username=(
                            docker_credentials.get("username")
                            if docker_credentials is not None
                            else None
                        ),
                        docker_credentials_password=(
                            docker_credentials.get("password")
                            if docker_credentials is not None
                            else None
                        ),
                        healthcheck=(
                            HealthCheck.objects.create(
                                type=healthcheck["type"].upper(),
                                value=healthcheck["value"],
                                timeout_seconds=healthcheck["timeout_seconds"],
                                interval_seconds=healthcheck["interval_seconds"],
                            )
                            if healthcheck is not None
                            else None
                        ),
                    )
                except IntegrityError:
                    raise ResourceConflict(
                        detail=f"A service with the slug `{service_slug}` already exists."
                    )

                # Create volumes if exists
                volumes_request = data.get("volumes", [])
                created_volumes = Volume.objects.bulk_create(
                    [
                        Volume(
                            name=volume.get("name", fake.slug().lower()),
                            container_path=volume["mount_path"],
                            host_path=volume.get("host_path"),
                        )
                        for volume in volumes_request
                    ]
                )

                service.volumes.add(*created_volumes)

                # create ports configuration
                service_urls_from_request = data.get("urls", [])
                ports_from_request = data.get("ports", [])
                http_ports = [80, 443]

                if len(service_urls_from_request) > 0:
                    has_at_least_one_http_port = False
                    for port in ports_from_request:
                        if port["public"] in http_ports:
                            has_at_least_one_http_port = True
                            break

                    if not has_at_least_one_http_port:
                        ports_from_request.append(
                            {
                                "public": 80,
                                "forwarded": 80,
                            }
                        )

                created_ports = PortConfiguration.objects.bulk_create(
                    [
                        PortConfiguration(
                            host=(
                                port["public"]
                                if port["public"] not in http_ports
                                else None
                            ),
                            forwarded=port["forwarded"],
                        )
                        for port in ports_from_request
                    ]
                )

                service.ports.add(*created_ports)

                # Create urls to route the service to
                can_create_urls = len(service_urls_from_request) > 0
                if not can_create_urls:
                    for port in ports_from_request:
                        public_port = port["public"]
                        if public_port in http_ports:
                            can_create_urls = True
                            break

                if can_create_urls:
                    if len(service_urls_from_request) == 0:
                        existing_urls = URL.objects.filter(
                            domain=f"{project.slug}-{service_slug}.{settings.ROOT_DOMAIN}",
                            base_path="/",
                        ).first()
                        if existing_urls is None:
                            default_url = URL.objects.create(
                                domain=f"{project.slug}-{service_slug}.{settings.ROOT_DOMAIN}",
                                base_path="/",
                            )
                        else:
                            default_url = URL.objects.create(
                                domain=f"{project.slug}-{service_slug}-{fake.slug()}.{settings.ROOT_DOMAIN}",
                                base_path="/",
                            )
                        service.urls.add(default_url)
                    else:
                        urls_to_create: list[URL] = []

                        for url in service_urls_from_request:
                            base_path = (
                                "/"
                                if url["base_path"] == "/"
                                else strip_slash_if_exists(
                                    url["base_path"],
                                    strip_end=True,
                                    strip_start=False,
                                )
                            )
                            urls_to_create.append(
                                URL(
                                    domain=url["domain"],
                                    base_path=base_path,
                                    strip_prefix=url["strip_prefix"],
                                )
                            )

                        created_urls = URL.objects.bulk_create(urls_to_create)
                        service.urls.add(*created_urls)

                # Create first deployment
                first_deployment = DockerDeployment.objects.create(
                    service=service, image_tag=docker_image_tag
                )
                if len(service.urls.all()) > 0:
                    first_deployment.url = f"{project.slug}-{service_slug}-{first_deployment.unprefixed_hash}.{settings.ROOT_DOMAIN}"
                    first_deployment.save()

                # Create envs if exists
                envs_from_request: dict[str, str] = data.get("env", {})

                DockerEnvVariable.objects.bulk_create(
                    [
                        DockerEnvVariable(key=key, value=value, service=service)
                        for key, value in envs_from_request.items()
                    ]
                )

                token = Token.objects.get(user=request.user)
                # Run celery deployment task
                transaction.on_commit(
                    lambda: deploy_docker_service.apply_async(
                        kwargs=dict(
                            deployment_hash=first_deployment.hash,
                            service_id=service.id,
                            auth_token=token.key,
                        ),
                        task_id=first_deployment.task_id,
                    )
                )

                response = DockerServiceResponseSerializer({"service": service})
                return Response(response.data, status=status.HTTP_201_CREATED)


class GetDockerServiceAPIView(APIView):
    serializer_class = DockerServiceResponseSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        operation_id="getDockerService",
    )
    def get(self, request: Request, project_slug: str, service_slug: str):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        response = DockerServiceResponseSerializer({"service": service})
        return Response(response.data, status=status.HTTP_200_OK)


class DockerServiceDeploymentFilter(django_filters.FilterSet):
    deployment_status = django_filters.MultipleChoiceFilter(
        choices=DockerDeployment.DeploymentStatus.choices
    )

    class Meta:
        model = DockerDeployment
        fields = ["deployment_status", "created_at", "hash"]


class DockerServiceDeploymentsAPIView(ListAPIView):
    serializer_class = serializers.DockerServiceDeploymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DockerServiceDeploymentFilter
    queryset = (
        DockerDeployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    def get_queryset(self) -> QuerySet[DockerDeployment]:
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except DockerRegistryService.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        return (
            DockerDeployment.objects.filter(service=service)
            .select_related("service", "is_redeploy_of")
            .order_by("-created_at")
        )


class DockerServiceDeploymentSingleAPIView(RetrieveAPIView):
    serializer_class = serializers.DockerServiceDeploymentSerializer
    lookup_url_kwarg = "deployment_hash"  # This corresponds to the URL configuration
    queryset = (
        DockerDeployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_object`

    def get_object(self):
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        deployment_hash = self.kwargs["deployment_hash"]

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            service = DockerRegistryService.objects.get(
                slug=service_slug, project=project
            )
            deployment: DockerDeployment | None = (
                DockerDeployment.objects.filter(service=service, hash=deployment_hash)
                .select_related("service", "is_redeploy_of")
                .first()
            )
            if deployment is None:
                raise DockerDeployment.DoesNotExist("")
            return deployment
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except DockerRegistryService.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )
        except DockerDeployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )


class ArchiveDockerServiceAPIView(APIView):
    @extend_schema(
        responses={
            204: inline_serializer(
                name="AchiveDockerServiveResponseSerializer", fields={}
            ),
        },
        operation_id="archiveDockerService",
    )
    @transaction.atomic()
    def delete(self, request: Request, project_slug: str, service_slug: str):
        project = (
            Project.objects.filter(
                slug=project_slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )

        service: DockerRegistryService = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )

        archived_project = (
            project.archived_version if hasattr(project, "archived_version") else None
        )
        if archived_project is None:
            archived_project = ArchivedProject.create_from_project(project)

        archived_service = ArchivedDockerService.create_from_service(
            service, archived_project
        )

        archive_task_id = service.archive_task_id
        service.delete_resources()
        service.delete()

        transaction.on_commit(
            lambda: delete_resources_for_docker_service.apply_async(
                kwargs=dict(archived_service_id=archived_service.id),
                task_id=archive_task_id,
            )
        )

        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)
