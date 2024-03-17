from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..models import Project, DockerRegistryService, DockerDeployment, Volume, EnvVariable, PortConfiguration
from ..services import create_service_from_docker_registry, size_in_bytes, create_docker_volume


class DockerCredentialsSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)
    registry_url = serializers.URLField(required=False)


class ServicePortsSerializer(serializers.Serializer):
    public = serializers.IntegerField(required=False)
    private = serializers.IntegerField()


class VolumeSizeSerializer(serializers.Serializer):
    n = serializers.IntegerField()
    unit = serializers.ChoiceField(choices=['B', 'MB', 'KB', 'GB'], default='B')


class VolumeSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    size = VolumeSizeSerializer(required=False)
    mount_path = serializers.CharField(max_length=255)


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    image = serializers.CharField(required=True)
    credentials = DockerCredentialsSerializer(required=False)
    domain = serializers.URLField(required=False)
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
            service = DockerRegistryService.objects.create(
                name=data['name'],
                slug=slugify(data["name"]),
                project=project,
                image=data['image'],
                command=data.get('command'),
            )

            # Create volumes if exists
            volumes_request = data.get('volumes', [])
            created_volumes = Volume.objects.bulk_create([
                Volume(
                    name=volume['name'],
                    slug=slugify(volume["name"]),
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

            PortConfiguration.objects.bulk_create([
                PortConfiguration(
                    project=project,
                    host=port.get('public'),
                    forwarded=port['private'],
                ) for port in ports_from_request
            ])

            # Create service in docker
            create_service_from_docker_registry(service)

            # 2. Create first deployment
            first_deployment = DockerDeployment.objects.create(
                service=service
            )

            response = self.serializer_class({})
            return Response(response.data, status=status.HTTP_201_CREATED)

        return Response(data=form.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
