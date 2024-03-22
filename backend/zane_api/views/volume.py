from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..docker_utils import get_docker_volume_size
from ..models import Volume


class VolumeGetSizeSuccessResponseSerializer(serializers.Serializer):
    size = serializers.IntegerField()


class VolumeGetSizeView(APIView):
    serializer_class = VolumeGetSizeSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = serializers.BaseErrorResponseSerializer

    @extend_schema(
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            404: error_serializer_class,
        },
        operation_id="getVolumeSize"
    )
    def get(self, request: Request, slug: str):
        try:
            volume = Volume.objects.get(slug=slug)
        except Volume.DoesNotExist:
            response = self.error_serializer_class({
                'errors': {
                    'root': [f"A volume with the slug `{slug}` does not exist"]
                }
            })
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)
        else:
            size = get_docker_volume_size(volume)
            response = self.serializer_class(dict(size=size))
            return Response(response.data)
