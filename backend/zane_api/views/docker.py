from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import serializers, permissions
from temporal.helpers import (
    search_images_docker_hub,
)


class DockerImageSerializer(serializers.Serializer):
    full_image = serializers.CharField(max_length=255)
    description = serializers.CharField()


class DockerImageSearchResponseSerializer(serializers.Serializer):
    images = DockerImageSerializer(many=True)


class DockerImageSearchParamsSerializer(serializers.Serializer):
    q = serializers.CharField(required=True)


class DockerImageSearchView(APIView):
    serializer_class = DockerImageSearchResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

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
            result = search_images_docker_hub(term=params["q"])  # type: ignore
            response = DockerImageSearchResponseSerializer({"images": result})
            return Response(response.data, status=status.HTTP_200_OK)
