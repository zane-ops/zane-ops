from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..temporal.activities import get_server_resource_limits

from .. import serializers


class SettingsSerializer(serializers.Serializer):
    root_domain = serializers.CharField()
    image_version = serializers.CharField()
    commit_sha = serializers.CharField()


class SettingsView(APIView):
    serializer_class = SettingsSerializer

    @extend_schema(
        operation_id="getAPISettings",
        summary="Get API settings",
        description="Get the settings of the API.",
    )
    def get(self, _: Request) -> Response:
        response = SettingsSerializer(
            {
                "root_domain": settings.ROOT_DOMAIN,
                "image_version": settings.IMAGE_VERSION,
                "commit_sha": settings.COMMIT_SHA,
            }
        )

        return Response(response.data)


class ResourceLimitSerializer(serializers.Serializer):
    no_of_cpus = serializers.IntegerField()
    max_memory_in_bytes = serializers.IntegerField()


class ResourceLimitsView(APIView):
    serializer_class = ResourceLimitSerializer

    @extend_schema(
        operation_id="getServerResouceLimits",
        summary="Get server resource limits",
        description="Get the number of CPUS & memory of the server.",
    )
    def get(self, _: Request) -> Response:
        no_of_cpus, max_memory_in_bytes = get_server_resource_limits()
        response = ResourceLimitSerializer(
            dict(max_memory_in_bytes=max_memory_in_bytes, no_of_cpus=no_of_cpus)
        )

        return Response(response.data)
