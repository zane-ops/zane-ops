import requests
from rest_framework import serializers, status
from ..models import ContainerRegistryCredentials


class ContainerRegistryCredentialsSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs: dict):
        url = attrs["url"]
        username = attrs.get("username")
        password = attrs.get("password")

        # we already assume this is a valid docker registry
        response = requests.get(f"{url}/v2/", timeout=10)
        headers = response.headers

        match response.status_code:
            case status.HTTP_200_OK:
                attrs["username"] = None
                attrs["password"] = None
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
                            "This field is required for authenticated registries."
                        ]
                    if not password:
                        errors["password"] = [
                            "This field is required for authenticated registries."
                        ]
                    raise serializers.ValidationError(errors)

                if "Basic" in auth_header:
                    response = requests.get(
                        f"{url}/v2/", auth=(username, password), timeout=10
                    )
                    if not status.is_success(response.status_code):
                        raise serializers.ValidationError(
                            {
                                "non_field_errors": [
                                    "Authentication failed. Please check your credentials."
                                ]
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
                                "non_field_errors": [
                                    "Authentication failed. Please check your credentials."
                                ]
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
        fields = ["id", "registry_type", "username", "url", "password"]
        extra_kwargs = {"id": {"read_only": True}}
