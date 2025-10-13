from typing import cast
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView

from ..serializers import ContainerRegistryCredentialsSerializer
from ..models import ContainerRegistryCredentials
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from zane_api.views import (
    ErrorResponse409Serializer,
    ResourceConflict,
)
from django.db import transaction, IntegrityError
from rest_framework.request import Request
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status


class ContainerRegistryCredentialsListAPIView(ListCreateAPIView):
    serializer_class = ContainerRegistryCredentialsSerializer
    queryset = ContainerRegistryCredentials.objects.all()
    pagination_class = None

    @extend_schema(
        operation_id="getRegistryCredentials",
        summary="List all container registry credentials",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        responses={
            409: ErrorResponse409Serializer,
            201: ContainerRegistryCredentialsSerializer,
        },
        operation_id="createRegistryCredentials",
        summary="Create new Registry credentials",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    # @transaction.atomic()
    # def create(self, request: Request, *args, **kwargs):
    #     form = CreateSSHKeyRequestSerializer(data=request.data)
    #     form.is_valid(raise_exception=True)

    #     data = cast(ReturnDict, form.data)
    #     slug: str = data["slug"]
    #     public_key, private_key = SSHKey.create_key_pair()
    #     try:
    #         new_key = SSHKey.objects.create(
    #             user=data["user"],
    #             slug=slug,
    #             public_key=public_key,
    #             private_key=private_key,
    #             fingerprint=SSHKey.generate_fingerprint(public_key),
    #         )
    #     except IntegrityError:
    #         raise ResourceConflict(
    #             detail=f"An SSH Key with the slug `{slug}` already exists"
    #         )
    #     else:
    #         response = SSHKeySerializer(new_key)
    #         return Response(response.data, status=status.HTTP_201_CREATED)
