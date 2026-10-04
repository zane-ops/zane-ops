from typing import cast
from django.db import transaction
from drf_spectacular.utils import extend_schema

from rest_framework import exceptions, status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    DestroyAPIView,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework.views import APIView

from zane_api.permissions import IsInstanceOwner
from zane_api.views.base import DefaultPageNumberPagination, EMPTY_PAGINATED_RESPONSE

from swarm.models import SSHKey, SwarmNode
from temporal.client import TemporalClient
from temporal.shared import SwarmNodeDetails, SwarmNodePair
from temporal.workflows import ProvisionSwarmNodeWorkflow
from swarm.serializers import (
    CreateSSHKeyRequestSerializer,
    ProvisionSwarmNodeRequestSerializer,
    SSHKeySerializer,
    FullSwarmNodeSerializer,
    UpdateSwarmNodeSSHPortSerializer,
    SwarmNodeSerializer,
)


class SwarmNodeListAPIView(ListCreateAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SwarmNodeSerializer
    queryset = SwarmNode.objects.all().order_by("hostname").prefetch_related("ssh_keys")
    pagination_class = DefaultPageNumberPagination

    @extend_schema(
        summary="Add new Swarm node to ZaneOps cluster",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

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


class SwarmNodeDetailsAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsInstanceOwner]
    queryset = SwarmNode.objects.prefetch_related("ssh_keys").all()
    lookup_field = "id"
    http_method_names = ["get", "patch"]

    def get_serializer_class(self):  # type: ignore
        if self.request.method == "PATCH":
            return UpdateSwarmNodeSSHPortSerializer
        return FullSwarmNodeSerializer

    @extend_schema(
        operation_id="updateSwarmNode",
        summary="Update a swarm node",
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class MainSwarmNodeAPIView(APIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = FullSwarmNodeSerializer

    @extend_schema(
        responses={200: FullSwarmNodeSerializer},
        operation_id="getMainSwarmNode",
        summary="Get the main server of the ZaneOps cluster",
    )
    def get(self, request: Request):
        try:
            node = (
                SwarmNode.objects.filter(is_initial_install_server=True)
                .prefetch_related("ssh_keys")
                .get()
            )
        except SwarmNode.DoesNotExist:
            raise exceptions.NotFound("No main server exists on the cluster")

        return Response(FullSwarmNodeSerializer(node).data)


class SwarmNodeSSHKeysAPIView(APIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SSHKeySerializer

    @extend_schema(
        request=CreateSSHKeyRequestSerializer,
        responses={201: SSHKeySerializer},
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
        public_key, private_key = SSHKey.create_key_pair()
        new_key = SSHKey.objects.create(
            node=node,
            user=data["user"],
            name=data["name"],
            public_key=public_key,
            private_key=private_key,
            fingerprint=SSHKey.generate_fingerprint(public_key),
        )

        response = SSHKeySerializer(new_key)
        return Response(response.data, status=status.HTTP_201_CREATED)


class SwarmNodeSSHKeyDetailsAPIView(DestroyAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SSHKeySerializer
    lookup_field = "id"
    lookup_url_kwarg = "key_id"

    def get_queryset(self):  # type: ignore
        id = self.kwargs["id"]
        try:
            node = SwarmNode.objects.get(id=id)
        except SwarmNode.DoesNotExist:
            raise exceptions.NotFound(f"A server with the id `{id}` does not exist")

        return SSHKey.objects.filter(node=node)


class ProvisionSwarmNodeAPIView(APIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = FullSwarmNodeSerializer

    @extend_schema(
        request=ProvisionSwarmNodeRequestSerializer,
        responses={202: FullSwarmNodeSerializer},
        operation_id="provisionSwarmNode",
        summary="Provision a swarm node and add it to the ZaneOps cluster",
    )
    @transaction.atomic()
    def post(self, request: Request, id: str):
        try:
            node = SwarmNode.objects.get(id=id)
        except SwarmNode.DoesNotExist:
            raise exceptions.NotFound(f"A server with the id `{id}` does not exist")

        main_node = SwarmNode.objects.filter(is_initial_install_server=True).first()

        form = ProvisionSwarmNodeRequestSerializer(
            data=request.data, context={"target_node": node, "main_node": main_node}
        )
        form.is_valid(raise_exception=True)
        main_node = cast(SwarmNode, main_node)

        data = cast(ReturnDict, form.data)
        target_key = node.ssh_keys.get(id=data["target_ssh_key_id"])
        main_key = main_node.ssh_keys.get(id=data["main_ssh_key_id"])

        payload = SwarmNodePair(
            target_node=SwarmNodeDetails(
                id=node.id,
                private_ip=node.private_ip,
                swarm_role=node.swarm_role,  # type: ignore
                cluster_roles=node.cluster_roles,  # type: ignore
                ssh_key=target_key.private_key,
                ssh_port=node.ssh_port,
            ),
            main_node=SwarmNodeDetails(
                id=main_node.id,
                private_ip=main_node.private_ip,
                swarm_role=main_node.swarm_role,  # type: ignore
                cluster_roles=main_node.cluster_roles,  # type: ignore
                ssh_key=main_key.private_key,
                ssh_port=main_node.ssh_port,
            ),
        )

        workflow_id = node.provision_swarm_node_workflow_id
        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                ProvisionSwarmNodeWorkflow.run,
                payload,
                id=workflow_id,
            )
        )

        response = FullSwarmNodeSerializer(node)
        return Response(response.data, status=status.HTTP_202_ACCEPTED)
