import docker.errors
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from faker import Faker
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..models import Project, DockerRegistryService, DockerDeployment, Volume, EnvVariable, PortConfiguration, URL
from ..services import create_service_from_docker_registry, create_docker_volume, \
    login_to_docker_registry, pull_docker_image, check_if_port_is_available


class DockerCredentialsRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)
    registry_url = serializers.URLField(required=False)


class ServicePortsRequestSerializer(serializers.Serializer):
    public = serializers.IntegerField(required=False, default=80)
    forwarded = serializers.IntegerField()


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    mount_path = serializers.CharField(max_length=255)


class URLRequestSerializer(serializers.Serializer):
    domain = serializers.URLDomainField(required=True)
    base_path = serializers.URLPathField(required=False, default="/")


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    image = serializers.CharField(required=True)
    credentials = DockerCredentialsRequestSerializer(required=False)
    urls = URLRequestSerializer(many=True, required=False)
    command = serializers.CharField(required=False)
    ports = ServicePortsRequestSerializer(required=False, many=True)
    env = serializers.DictField(child=serializers.CharField(), required=False)
    volumes = VolumeRequestSerializer(many=True, required=False)

    def validate(self, data: dict):
        credentials = data.get('credentials')
        image = data.get('image')

        try:
            pull_docker_image(image, auth=dict(credentials) if credentials is not None else None)
        except docker.errors.NotFound:
            registry = credentials.get('registry_url') if credentials is not None else None
            if registry is None:
                registry = "Docker Hub's Registry"
            else:
                registry = f"the registry at {registry}"
            raise serializers.ValidationError({
                'image': [f"The image `{image}` does not exist on {registry}"]
            })
        except docker.errors.APIError:
            raise serializers.ValidationError({
                'image': [f"This image does not correspond to the credentials provided"]
            })

        return data

    def validate_credentials(self, value: dict):
        try:
            login_to_docker_registry(
                username=value['username'],
                password=value['password'],
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
            public_port = port['public']

            # Check for only 1 http port
            if public_port in http_ports:
                no_of_http_ports += 1
            if no_of_http_ports > 1:
                raise serializers.ValidationError("Only one HTTP port is allowed")

            # Check for duplicate public ports
            if public_port in public_ports_seen:
                raise serializers.ValidationError("Duplicate public port values are not allowed.")
            if public_port not in http_ports:
                public_ports_seen.add(public_port)

            # check if port is available
            is_port_available = check_if_port_is_available(public_port)
            if not is_port_available:
                raise serializers.ValidationError(f"Port {public_port} is not available on the host machine.")

        already_existing_ports = [
            str(port.host) for port in PortConfiguration.objects.filter(host__in=list(public_ports_seen))
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
        # Check for duplicate public ports
        urls_seen = set()
        for url in value:
            new_url = (url['domain'], url['base_path'])
            if new_url in urls_seen:
                raise serializers.ValidationError("Duplicate urls values are not allowed.")
            urls_seen.add(new_url)
        return value


class DockerServiceCreateSuccessResponseSerializer(serializers.Serializer):
    service = serializers.DockerServiceSerializer(read_only=True)


class DockerServiceCreateErrorSerializer(serializers.BaseErrorSerializer):
    name = serializers.StringListField(required=False)
    image = serializers.StringListField(required=False)
    credentials = serializers.StringListField(required=False)
    urls = serializers.StringListField(required=False)
    command = serializers.StringListField(required=False)
    ports = serializers.StringListField(required=False)
    env = serializers.StringListField(required=False)
    volumes = serializers.StringListField(required=False)


class DockerServiceCreateErrorResponseSerializer(serializers.Serializer):
    errors = DockerServiceCreateErrorSerializer()


class CreateDockerServiceAPIView(APIView):
    serializer_class = DockerServiceCreateSuccessResponseSerializer
    error_serializer_class = DockerServiceCreateErrorResponseSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            422: error_serializer_class,
            404: error_serializer_class,
            409: error_serializer_class,
            201: serializer_class,
            403: serializers.ForbiddenResponseSerializer
        },
        operation_id="createDockerService",
    )
    @transaction.atomic()
    def post(self, request: Request, project_slug: str):
        try:
            project = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [f"A project with the slug `{project_slug}` does not exist"],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)
        else:
            form = DockerServiceCreateRequestSerializer(data=request.data)
            if form.is_valid():
                data = form.data

                # Create service in DB
                docker_credentials: dict | None = data.get('credentials')
                service_slug = slugify(data["name"])
                try:
                    service = DockerRegistryService.objects.create(
                        name=data['name'],
                        slug=service_slug,
                        project=project,
                        image=data['image'],
                        command=data.get('command'),
                        docker_credentials_username=docker_credentials.get(
                            'username') if docker_credentials is not None else None,
                        docker_credentials_password=docker_credentials.get(
                            'password') if docker_credentials is not None else None,
                    )
                except IntegrityError:
                    response = self.error_serializer_class(
                        {
                            "errors": {
                                "root": [
                                    "A service with a similar slug already exist in this project,"
                                    " please use another name for this service"
                                ]
                            }
                        }
                    )
                    return Response(response.data, status=status.HTTP_409_CONFLICT)

                # Create volumes if exists
                fake = Faker()
                volumes_request = data.get('volumes', [])
                created_volumes = Volume.objects.bulk_create([
                    Volume(
                        name=volume['name'],
                        slug=f"{service.slug}-{fake.slug()}",
                        project=project,
                        containerPath=volume['mount_path'],
                    ) for volume in volumes_request
                ])

                service.volumes.add(*created_volumes)

                # Create envs if exists
                envs_from_request: dict[str, str] = data.get('env', {})

                created_envs = EnvVariable.objects.bulk_create([
                    EnvVariable(
                        key=key,
                        value=value,
                        project=project,
                    ) for key, value in envs_from_request.items()
                ])

                service.env_variables.add(*created_envs)

                # create ports configuration
                ports_from_request = data.get('ports', [])

                created_ports = PortConfiguration.objects.bulk_create([
                    PortConfiguration(
                        project=project,
                        host=port['public'],
                        forwarded=port['forwarded'],
                    ) for port in ports_from_request
                ])

                service.port_config.add(*created_ports)

                # Create urls to route the service to
                http_ports = [80, 443]

                can_create_urls = False
                for port in ports_from_request:
                    public_port = port['public']
                    if public_port in http_ports:
                        can_create_urls = True
                        break

                if can_create_urls:
                    service_urls = data.get("urls", [])
                    if len(service_urls) == 0:
                        default_url = URL.objects.create(
                            domain=f"{project.slug}-{service_slug}.{settings.ROOT_DOMAIN}",
                            base_path="/"
                        )
                        service.urls.add(default_url)
                    else:
                        created_urls = URL.objects.bulk_create([
                            URL(domain=url['domain'], base_path=url['base_path']) for url in service_urls
                        ])
                        service.urls.add(*created_urls)

                # Create first deployment
                DockerDeployment.objects.create(
                    service=service
                )

                # Create resources in docker
                for volume in created_volumes:
                    create_docker_volume(volume)
                create_service_from_docker_registry(service)

                response = self.serializer_class({"service": service})
                return Response(response.data, status=status.HTTP_201_CREATED)

            response = self.error_serializer_class({"errors": form.errors})
            return Response(data=response.data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class GetDockerServiceAPIView(APIView):
    serializer_class = DockerServiceCreateSuccessResponseSerializer
    error_serializer_class = serializers.BaseErrorResponseSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            404: error_serializer_class,
            200: serializer_class,
            403: serializers.ForbiddenResponseSerializer
        },
        operation_id="getDockerService",
    )
    def get(self, request: Request, project_slug: str, service_slug: str):
        try:
            project = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [f"A project with the slug `{project_slug}` does not exist"],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)

        service = ((DockerRegistryService.objects.filter(
            Q(slug=service_slug) & Q(project=project))
                    .select_related("project")
                    .prefetch_related("volumes", "port_config", "env_variables", "urls"))
                   .first())

        if service is None:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [f"A service with the slug `{service_slug}`"
                                 f" does not exist within the project `{project_slug}`"],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)

        response = self.serializer_class({"service": service})
        return Response(response.data, status=status.HTTP_200_OK)
