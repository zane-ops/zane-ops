from typing import cast
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema

from rest_framework import exceptions, status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework.views import APIView

from zane_api.permissions import IsInstanceOwner
from zane_api.views import ErrorResponse409Serializer, ResourceConflict
from zane_api.views.base import DefaultPageNumberPagination, EMPTY_PAGINATED_RESPONSE

from swarm.models import SwarmNode
from swarm.serializers import SwarmNodeSerializer
from webshell.models import SSHKey
from webshell.serializers import CreateSSHKeyRequestSerializer, SSHKeySerializer


class SwarmNodeListAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SwarmNodeSerializer
    queryset = SwarmNode.objects.all().order_by("hostname").prefetch_related("ssh_keys")
    pagination_class = DefaultPageNumberPagination

    @extend_schema(
        summary="List all swarm nodes in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e


class SwarmNodeDetailsAPIView(RetrieveAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SwarmNodeSerializer
    queryset = SwarmNode.objects.prefetch_related("ssh_keys").all()
    lookup_field = "id"


class SwarmNodeSSHKeysAPIView(APIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SSHKeySerializer

    @extend_schema(
        request=CreateSSHKeyRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            201: SSHKeySerializer,
        },
        operation_id="createSwarmNodeSSHKey",
        summary="Create a new SSH key attached to this swarm node",
    )
    def post(self, request: Request, id: str):
        try:
            node = SwarmNode.objects.get(id=id)
        except SwarmNode.DoesNotExist:
            raise exceptions.NotFound(f"A server with the id `{id}` does not exist")

        form = CreateSSHKeyRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(ReturnDict, form.data)
        slug: str = data["slug"]
        public_key, private_key = SSHKey.create_key_pair()
        try:
            new_key = SSHKey.objects.create(
                user=data["user"],
                slug=slug,
                public_key=public_key,
                private_key=private_key,
                fingerprint=SSHKey.generate_fingerprint(public_key),
            )
        except IntegrityError:
            raise ResourceConflict(
                detail=f"An SSH Key with the slug `{slug}` already exists"
            )

        node.ssh_keys.add(new_key)
        response = SSHKeySerializer(new_key)
        return Response(response.data, status=status.HTTP_201_CREATED)
