from django.shortcuts import render
from rest_framework.generics import ListCreateAPIView
from .serializers import SSHKeySerializer, SSHKeyListFilterSet, SSHKeyListPagination
from django_filters.rest_framework import DjangoFilterBackend
from .models import SSHKey
from rest_framework import exceptions
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from zane_api.views import EMPTY_PAGINATED_RESPONSE, ErrorResponse409Serializer


class SSHKeyListAPIView(ListCreateAPIView):
    serializer_class = SSHKeySerializer
    filter_backends = [DjangoFilterBackend]
    queryset = (
        SSHKey.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`
    pagination_class = SSHKeyListPagination
    filterset_class = SSHKeyListFilterSet

    @extend_schema(operation_id="getSSHKeyList", summary="List all ssh keys")
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound:
            return Response(EMPTY_PAGINATED_RESPONSE)

    @extend_schema(
        # request=ProjectCreateRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            201: SSHKeySerializer,
        },
        operation_id="createSSHKey",
        summary="Create a new SSH key",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
