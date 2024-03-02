from typing import TypedDict

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..services import docker_client


class DockerImageSerializer(serializers.Serializer):
    full_image = serializers.CharField(max_length=255)
    description = serializers.CharField()


class DockerSuccessResponseSerializer(serializers.Serializer):
    images = DockerImageSerializer(many=True)


class DockerImageListSearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=True)


class DockerImageResultFromSearch(TypedDict):
    name: str
    description: str
    is_official: bool


class DockerServiceView(APIView):
    serializer_class = DockerSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = serializers.ErrorResponseSerializer

    @extend_schema(
        parameters=[
            DockerImageListSearchSerializer,
        ],
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
        },
        operation_id="searchDockerRegistry",
    )
    def get(self, request: Request):
        query_params = request.query_params.dict()
        form = DockerImageListSearchSerializer(data=query_params)

        if form.is_valid():
            params = form.data
            result: list[DockerImageResultFromSearch] = docker_client.images.search(term=params['q'], limit=30)

            images_to_return = []
            for image in result:
                api_image_result = {}
                if image['is_official']:
                    api_image_result['full_image'] = f'library/{image["name"]}:latest'
                else:
                    api_image_result['full_image'] = f'{image["name"]}:latest'
                api_image_result['description'] = image['description']
                images_to_return.append(api_image_result)

            response = self.serializer_class({'images': images_to_return})
            return Response(response.data, status=status.HTTP_200_OK)

        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data={"errors": form.errors},
        )
