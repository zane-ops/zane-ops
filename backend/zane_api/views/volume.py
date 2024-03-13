from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class VolumeGetSizeView(APIView):
    @extend_schema()
    def get(self, request: Request, slug: str):
        return Response()
