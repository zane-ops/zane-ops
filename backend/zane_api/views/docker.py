from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..services import (
    search_docker_registry,
    check_if_port_is_available,
    login_to_docker_registry
)


class DockerImageSerializer(serializers.Serializer):
    full_image = serializers.CharField(max_length=255)
    description = serializers.CharField()


class DockerSuccessResponseSerializer(serializers.Serializer):
    images = DockerImageSerializer(many=True)


class DockerImageListSearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=True)


class DockerImageSearchErrorSerializer(serializers.BaseErrorSerializer):
    q = serializers.StringListField(required=False)


class DockerImageSearchErrorResponseSerializer(serializers.Serializer):
    errors = DockerImageSearchErrorSerializer()


class DockerImageSearchView(APIView):
    serializer_class = DockerSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = DockerImageSearchErrorResponseSerializer

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
            result = search_docker_registry(term=params["q"])
            response = self.serializer_class({"images": result})
            return Response(response.data, status=status.HTTP_200_OK)

        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data={"errors": form.errors},
        )


class DockerLoginSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class DockerLoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(max_length=255, required=True)
    registry_url = serializers.URLField(required=False)


class DockerLoginErrorSerializer(serializers.BaseErrorSerializer):
    username = serializers.StringListField(required=False)
    password = serializers.StringListField(required=False)
    registry_url = serializers.StringListField(required=False)


class DockerLoginErrorResponseSerializer(serializers.Serializer):
    errors = DockerLoginErrorSerializer()


class DockerLoginView(APIView):
    serializer_class = DockerLoginSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = DockerLoginErrorResponseSerializer

    @extend_schema(
        request=DockerLoginRequestSerializer,
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
            401: error_serializer_class,
        },
        operation_id="dockerLogin",
    )
    def post(self, request: Request):
        form = DockerLoginRequestSerializer(data=request.data)

        if form.is_valid():
            data = form.data
            result = login_to_docker_registry(**data)

            if not result:
                response = self.error_serializer_class(
                    {"errors": {"root": ["Invalid credentials"]}}
                )
                return Response(response.data, status=status.HTTP_401_UNAUTHORIZED)

            response = self.serializer_class({"success": result})
            return Response(response.data, status=status.HTTP_200_OK)

        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data={"errors": form.errors},
        )


class DockerPortCheckSuccessResponseSerializer(serializers.Serializer):
    available = serializers.BooleanField()


class DockerPortCheckRequestSerializer(serializers.Serializer):
    port = serializers.IntegerField(required=True, min_value=0)


class DockerPortCheckErrorSerializer(serializers.BaseErrorSerializer):
    port = serializers.StringListField(required=False)


class DockerPortCheckErrorResponseSerializer(serializers.Serializer):
    errors = DockerPortCheckErrorSerializer()


class DockerPortCheckView(APIView):
    serializer_class = DockerPortCheckSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = DockerPortCheckErrorResponseSerializer

    @extend_schema(
        request=DockerPortCheckRequestSerializer,
        responses={
            200: serializer_class,
            400: serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
        },
        operation_id="checkIfPortIsAvailable",
    )
    def post(self, request: Request):
        form = DockerPortCheckRequestSerializer(data=request.data)

        if form.is_valid():
            data = form.data
            result = check_if_port_is_available(port=data["port"])

            response = self.serializer_class({"available": result})
            return Response(
                response.data,
                status=status.HTTP_200_OK if result else status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data={"errors": form.errors},
        )
