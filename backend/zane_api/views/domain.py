from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers


class GetRootDomainSerializer(serializers.Serializer):
    domain = serializers.CharField()


class AuthedForbiddenResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class GetRootDomainView(APIView):
    """
    CSRF cookie view for retrieving CSRF before doing requests
    """

    serializer_class = GetRootDomainSerializer
    error_serializer_class = AuthedForbiddenResponseSerializer

    @extend_schema(
        responses={
            200: serializer_class,
            403: error_serializer_class,
        },
        operation_id="getRootDomain",
    )
    def get(self, _: Request) -> Response:
        response = GetRootDomainSerializer(data={"domain": settings.ROOT_DOMAIN})

        if response.is_valid():
            return Response(response.data)

        return Response(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            data={"errors": {".": response.errors}},
        )
