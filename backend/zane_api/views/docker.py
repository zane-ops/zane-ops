from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..temporal import search_images_docker_hub, check_if_port_is_available_on_host


class DockerImageSerializer(serializers.Serializer):
    full_image = serializers.CharField(max_length=255)
    description = serializers.CharField()


class DockerImageSearchResponseSerializer(serializers.Serializer):
    images = DockerImageSerializer(many=True)


class DockerImageSearchParamsSerializer(serializers.Serializer):
    q = serializers.CharField(required=True)


class DockerImageSearchView(APIView):
    serializer_class = DockerImageSearchResponseSerializer

    @extend_schema(
        parameters=[
            DockerImageSearchParamsSerializer,
        ],
        operation_id="searchDockerRegistry",
        summary="Search docker hub",
        description="Search a docker Image in docker hub Registry",
    )
    def get(self, request: Request):
        query_params = request.query_params.dict()
        form = DockerImageSearchParamsSerializer(data=query_params)

        if form.is_valid(raise_exception=True):
            params = form.data
            result = search_images_docker_hub(term=params["q"])
            response = DockerImageSearchResponseSerializer({"images": result})
            return Response(response.data, status=status.HTTP_200_OK)


class DockerLoginSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class DockerLoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(max_length=255, required=True)
    registry_url = serializers.URLField(required=False)


class DockerPortCheckResponseSerializer(serializers.Serializer):
    available = serializers.BooleanField()


class DockerPortCheckRequestSerializer(serializers.Serializer):
    port = serializers.IntegerField(required=True, min_value=0)


class DockerPortCheckView(APIView):
    serializer_class = DockerPortCheckResponseSerializer

    @extend_schema(
        request=DockerPortCheckRequestSerializer,
        operation_id="checkIfPortIsAvailable",
        summary="Check Port",
        description="Check If Port is available on host machine",
    )
    def post(self, request: Request):
        form = DockerPortCheckRequestSerializer(data=request.data)

        if form.is_valid(raise_exception=True):
            data = form.data
            result = check_if_port_is_available_on_host(port=data["port"])

            response = DockerPortCheckResponseSerializer({"available": result})
            return Response(
                response.data,
                status=status.HTTP_200_OK,
            )
