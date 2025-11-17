import django_filters
import requests
from rest_framework import serializers, status

from ..models import ContainerRegistryCredentials
from urllib.parse import urlparse
from ..constants import GITHUB_REGISTRY_URL, DOCKER_HUB_REGISTRY_URL


class ContainerRegistryCredentialsFilterSet(django_filters.FilterSet):
    class Meta:
        model = ContainerRegistryCredentials
        fields = ["registry_type"]


class ContainerRegistryListCreateCredentialsSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    registry_type = serializers.ChoiceField(
        choices=ContainerRegistryCredentials.RegistryType.choices,
        default=ContainerRegistryCredentials.RegistryType.DOCKER_HUB,
    )

    def validate(self, attrs: dict):
        registry_type = attrs.get(
            "registry_type",
            self.instance.registry_type if self.instance is not None else None,
        )

        # Override the registry URL in these cases
        match registry_type:
            case ContainerRegistryCredentials.RegistryType.DOCKER_HUB:
                attrs["url"] = DOCKER_HUB_REGISTRY_URL
            case ContainerRegistryCredentials.RegistryType.GITHUB:
                attrs["url"] = GITHUB_REGISTRY_URL

        parsed_url = urlparse(attrs["url"])
        url = attrs["url"] = parsed_url.scheme + "://" + parsed_url.netloc

        username = attrs["username"]
        password = attrs["password"]

        # we already assume this is a valid docker registry
        response = requests.get(f"{url}/v2/", timeout=10)
        headers = response.headers

        match response.status_code:
            case status.HTTP_200_OK:
                raise serializers.ValidationError(
                    f"Registry at '{url}' does not requires authentication, "
                    "ZaneOps only supports authenticated registries, "
                    "you don't need to add credentials for public registries",
                )
            case status.HTTP_401_UNAUTHORIZED:
                auth_header = headers.get("www-authenticate", "")

                if not auth_header:
                    raise serializers.ValidationError(
                        f"Registry at '{url}' requires authentication but didn't provide authentication details."
                    )

                if not (username and password):
                    errors = {}
                    if not username:
                        errors["username"] = [
                            "This registry requires authentication. Please provide a username."
                        ]
                    if not password:
                        errors["password"] = [
                            "This registry requires authentication. Please provide a password."
                        ]
                    raise serializers.ValidationError(errors)

                if "Basic" in auth_header:
                    response = requests.get(
                        f"{url}/v2/", auth=(username, password), timeout=10
                    )
                    if not status.is_success(response.status_code):
                        raise serializers.ValidationError(
                            {
                                "username": [
                                    "Authentication failed. Please check your credentials."
                                ],
                                "password": [
                                    "Authentication failed. Please check your credentials."
                                ],
                            }
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
                        raise serializers.ValidationError(
                            f"Registry at '{url}' has invalid Bearer authentication configuration."
                        )

                    token_response = requests.get(
                        realm,
                        params={"service": service},
                        auth=(username, password),
                        timeout=10,
                    )

                    if not status.is_success(token_response.status_code):
                        raise serializers.ValidationError(
                            {
                                "username": [
                                    "Authentication failed. Please check your credentials."
                                ],
                                "password": [
                                    "Authentication failed. Please check your credentials."
                                ],
                            }
                        )

                    token = token_response.json().get("token")
                    if not token:
                        raise serializers.ValidationError(
                            f"Registry at '{url}' failed to provide an access token."
                        )

                    # Verify token works
                    response = requests.get(
                        f"{url}/v2/",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    if not status.is_success(response.status_code):
                        raise serializers.ValidationError(
                            {
                                "non_field_errors": [
                                    "Authentication failed. Invalid token received."
                                ]
                            }
                        )
                else:
                    raise serializers.ValidationError(
                        f"Registry at '{url}' requires an unsupported authentication method."
                    )
            case _:
                raise serializers.ValidationError(
                    f"The URL '{url}' does not appear to be a valid Docker registry. "
                    f"Please verify the URL points to a Docker Registry v2 API endpoint. "
                    f"(Server returned HTTP {response.status_code})"
                )
        return attrs

    def validate_url(self, url: str):
        try:
            response = requests.get(f"{url}/v2/", timeout=10)

            registry_detected = (
                response.headers.get("Docker-Distribution-Api-Version")
                == "registry/2.0"
            )

            if not registry_detected:
                raise serializers.ValidationError(
                    f"The URL '{url}' does not appear to be a valid Docker registry. "
                    f"Please verify the URL points to a Docker Registry v2 API endpoint. "
                    f"(Server returned HTTP {response.status_code})"
                )

            return url

        except requests.exceptions.Timeout:
            raise serializers.ValidationError(
                f"Connection to '{url}' timed out. "
                f"Please verify the registry is accessible and try again."
            )
        except requests.exceptions.ConnectionError:
            raise serializers.ValidationError(
                f"Unable to connect to '{url}'. "
                f"Please check the URL and ensure the registry is reachable."
            )
        except requests.exceptions.RequestException as e:
            raise serializers.ValidationError(
                f"Could not validate registry at '{url}'. Error: {str(e)}"
            )

    class Meta:
        model = ContainerRegistryCredentials
        fields = [
            "id",
            "registry_type",
            "username",
            "password",
            "url",
            "slug",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "registry_type": {"required": True},
            "username": {"required": True},
        }


class ContainerRegistryCredentialsUpdateDetailsSerializer(
    ContainerRegistryListCreateCredentialsSerializer
):
    password = serializers.CharField(required=False)
    registry_type = serializers.ChoiceField(
        choices=ContainerRegistryCredentials.RegistryType.choices,
        default=ContainerRegistryCredentials.RegistryType.DOCKER_HUB,
        read_only=True,
    )

    class Meta:  # type: ignore
        model = ContainerRegistryCredentials
        fields = [
            "id",
            "registry_type",
            "username",
            "url",
            "password",
            "slug",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "registry_type": {"read_only": True},
        }
