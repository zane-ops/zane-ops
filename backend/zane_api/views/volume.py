from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers
from ..models import Volume
from ..temporal import get_docker_volume_size_in_bytes


class VolumeGetSizeResponseSerializer(serializers.Serializer):
    size = serializers.IntegerField()


class VolumeGetSizeView(APIView):
    serializer_class = VolumeGetSizeResponseSerializer

    @extend_schema(
        operation_id="getVolumeSize",
        summary="Get volume size",
        description="Get the total data size in the volume, in bytes.",
    )
    def get(self, request: Request, volume_id: str):
        try:
            volume = Volume.objects.get(id=volume_id)
        except Volume.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A volume with the id `{volume_id}` does not exist"
            )
        else:
            size = get_docker_volume_size_in_bytes(volume.id)
            response = VolumeGetSizeResponseSerializer({"size": size})
            return Response(response.data)
