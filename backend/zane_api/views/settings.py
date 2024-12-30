from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
