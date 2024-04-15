from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers


class GetRootDomainSerializer(serializers.Serializer):
    domain = serializers.CharField()


class GetRootDomainView(APIView):
    serializer_class = GetRootDomainSerializer

    @extend_schema(
        operation_id="getRootDomain",
    )
    def get(self, _: Request) -> Response:
        response = GetRootDomainSerializer(data={"domain": settings.ROOT_DOMAIN})

        if response.is_valid():
            return Response(response.data)
