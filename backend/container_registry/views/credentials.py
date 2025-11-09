import requests
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import exceptions, status, serializers

from ..serializers import (
    ContainerRegistryListCreateCredentialsSerializer,
    ContainerRegistryCredentialsUpdateDetailsSerializer,
    ContainerRegistryCredentialsFilterSet,
)
from ..models import ContainerRegistryCredentials
from drf_spectacular.utils import extend_schema, inline_serializer
from zane_api.views import ErrorResponse409Serializer, ResourceConflict, BadRequest
from django_filters.rest_framework import DjangoFilterBackend
from zane_api.models import DeploymentChange


class ContainerRegistryCredentialsListAPIView(ListCreateAPIView):
    serializer_class = ContainerRegistryListCreateCredentialsSerializer
    queryset = ContainerRegistryCredentials.objects.all()
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = ContainerRegistryCredentialsFilterSet

    @extend_schema(
        operation_id="getRegistryCredentials",
        summary="List all container registry credentials",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TestContainerRegistryCredentialsAPIView(APIView):
    @extend_schema(
        responses={
            200: inline_serializer(
                "TestContainerRegistryCredentialsResponseSerializer",
                fields={"success": serializers.BooleanField()},
            ),
        },
        operation_id="testRegistryCredentials",
        summary="Test if the credentials for a registry are valid",
    )
    def get(self, request: Request, id: str):
        try:
            credentials = ContainerRegistryCredentials.objects.get(id=id)
        except ContainerRegistryCredentials.DoesNotExist:
            raise exceptions.NotFound(
                f"No Container Registry Credential with id `{id}` found"
            )

        url = credentials.url
        username = credentials.username
        password = credentials.password

        # we already assume this is a valid docker registry
        response = requests.get(f"{url}/v2/", timeout=10)
        headers = response.headers

        match response.status_code:
            case status.HTTP_200_OK:
                pass  # do nothing, successful response
            case status.HTTP_401_UNAUTHORIZED:
                auth_header = headers.get("www-authenticate", "")

                if not auth_header:
                    raise BadRequest(
                        f"Registry at '{url}' requires authentication but didn't provide authentication details."
                    )

                if "Basic" in auth_header:
                    response = requests.get(
                        f"{url}/v2/", auth=(username, password), timeout=10
                    )
                    if not status.is_success(response.status_code):
                        raise BadRequest(
                            "Authentication failed. Please verify or update your credentials."
                        )

                elif "Bearer" in auth_header:
                    parts = dict(
                        item.split("=", 1)
                        for item in auth_header.replace("Bearer ", "")
                        .replace('"', "")
                        .split(",")
                    )
                    realm = parts.get("realm")
                    service = parts.get("service")

                    if not realm:
                        raise BadRequest(
                            f"Registry at '{url}' has invalid Bearer authentication configuration."
                        )

                    token_response = requests.get(
                        realm,
                        params={"service": service},
                        auth=(username, password),
                        timeout=10,
                    )

                    if not status.is_success(token_response.status_code):
                        raise BadRequest(
                            "Authentication failed. Please verify or update your credentials."
                        )

                    token = token_response.json().get("token")
                    if not token:
                        raise BadRequest(
                            f"Registry at '{url}' failed to provide an access token."
                        )

                    # Verify token works
                    response = requests.get(
                        f"{url}/v2/",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    if not status.is_success(response.status_code):
                        raise BadRequest(
                            "Authentication failed. Invalid token received."
                        )
                else:
                    raise BadRequest(
                        f"Registry at '{url}' requires an unsupported authentication method."
                    )
            case _:
                raise BadRequest(
                    f"The URL '{url}' does not appear to be a valid Docker registry anymore. "
                    f"Please verify the URL still points to a Docker Registry v2 API endpoint. "
                    f"(Server returned HTTP {response.status_code})"
                )

        return Response(data={"success": True})


class ContainerRegistryCredentialsDetailsAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = ContainerRegistryCredentialsUpdateDetailsSerializer
    queryset = ContainerRegistryCredentials.objects.all()
    http_method_names = ["get", "put", "delete"]
    lookup_url_kwarg = "id"

    def get_object(self) -> ContainerRegistryCredentials:  # type: ignore
        return super().get_object()

    @extend_schema(
        responses={409: ErrorResponse409Serializer, 204: None},
        operation_id="deleteRegistryCredentials",
        summary="Delete registry credentials",
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.services.count() > 0:
            raise ResourceConflict(
                "You cannot delete this container registry because it is referenced by at least one service"
            )
        if instance.build_registries.count() > 0:
            raise ResourceConflict(
                "You cannot delete this container registry because it is referenced by at least one build registry"
            )

        changes = DeploymentChange.objects.filter(
            new_value__container_registry_credentials__id=instance.id,
            field=DeploymentChange.ChangeField.SOURCE,
        )
        if changes.count() > 0:
            raise ResourceConflict(
                "You cannot delete this container registry because it is referenced by at least one deployment"
            )

        return super().destroy(request, *args, **kwargs)
