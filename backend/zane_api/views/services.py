from django.conf import settings
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from faker import Faker
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..models import Project, DockerRegistryService, DockerDeployment, Volume, EnvVariable, PortConfiguration, URL
from ..services import create_service_from_docker_registry, size_in_bytes, create_docker_volume


class DockerCredentialsSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)
    registry_url = serializers.URLField(required=False)


class ServicePortsSerializer(serializers.Serializer):
    public = serializers.IntegerField(required=False)
    forwarded = serializers.IntegerField()


class VolumeSizeSerializer(serializers.Serializer):
    n = serializers.IntegerField()
    unit = serializers.ChoiceField(choices=['B', 'MB', 'KB', 'GB'], default='B')


class VolumeSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    size = VolumeSizeSerializer(required=False)
    mount_path = serializers.CharField(max_length=255)


class URLSerializer(serializers.Serializer):
    domain = serializers.URLDomainField(required=True)
    base_path = serializers.URLPathField(required=False)


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    image = serializers.CharField(required=True)
    credentials = DockerCredentialsSerializer(required=False)
    urls = URLSerializer(many=True, required=False)
    command = serializers.CharField(required=False)
    ports = ServicePortsSerializer(required=False, many=True)
    env = serializers.DictField(child=serializers.CharField(), required=False)
    volumes = VolumeSerializer(many=True, required=False)


class DockerServiceCreateSuccessResponseSerializer(serializers.Serializer):
    pass


class DockerServiceCreateErrorResponseSerializer(serializers.Serializer):
    pass


class CreateDockerServiceAPIView(APIView):
    serializer_class = DockerServiceCreateSuccessResponseSerializer
    error_serializer_class = DockerServiceCreateErrorResponseSerializer

    @extend_schema(
        request=DockerServiceCreateRequestSerializer,
        responses={
            422: error_serializer_class,
            201: serializer_class
        },
        operation_id="createDockerService",
    )
    def post(self, request: Request, project_slug: str):
        project = Project.objects.get(slug=project_slug)
        form = DockerServiceCreateRequestSerializer(data=request.data)
        if form.is_valid():
            data = form.data

            # Create service in DB
            service_slug = slugify(data["name"])
            service = DockerRegistryService.objects.create(
                name=data['name'],
                slug=service_slug,
                project=project,
                image=data['image'],
                command=data.get('command'),
            )

            # Create volumes if exists
            fake = Faker()
            volumes_request = data.get('volumes', [])
            created_volumes = Volume.objects.bulk_create([
                Volume(
                    name=volume['name'],
                    slug=f"{service.slug}-{fake.slug()}",
                    project=project,
                    size_limit=size_in_bytes(volume["size"]['n'], volume['size']['unit']) if volume.get(
                        "size") is not None else None,
                    containerPath=volume['mount_path'],
                ) for volume in volumes_request
            ])

            for volume in created_volumes:
                service.volumes.add(volume)
                create_docker_volume(volume)

            # Create envs if exists
            envs_from_request: dict[str, str] = data.get('env', {})

            created_envs = EnvVariable.objects.bulk_create([
                EnvVariable(
                    key=key,
                    value=value,
                    project=project,
                ) for key, value in envs_from_request.items()
            ])

            for env in created_envs:
                service.env_variables.add(env)

            # create ports configuration
            ports_from_request = data.get('ports', [])

            created_ports = PortConfiguration.objects.bulk_create([
                PortConfiguration(
                    project=project,
                    host=port.get('public'),
                    forwarded=port['forwarded'],
                ) for port in ports_from_request
            ])

            for port in created_ports:
                service.port_config.add(port)

            # Create service in docker
            create_service_from_docker_registry(service)

            # Create urls to route the service to
            if data['port']:
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

                    for url in created_urls:
                        service.urls.add(url)

            # Create first deployment
            first_deployment = DockerDeployment.objects.create(
                service=service
            )

            response = self.serializer_class({})
            return Response(response.data, status=status.HTTP_201_CREATED)

        return Response(data=form.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
