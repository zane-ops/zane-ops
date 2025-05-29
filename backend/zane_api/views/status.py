from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import serializers


class PINGSerializer(serializers.Serializer):
    ping = serializers.ChoiceField(choices=["pong"])


class PINGView(APIView):
    serializer_class = PINGSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        operation_id="ping",
        summary="Ping",
        description="simple healthcheck endpoint.",
    )
    def get(self, _: Request) -> Response:
        response = PINGSerializer({"ping": "pong"})
        return Response(response.data)
