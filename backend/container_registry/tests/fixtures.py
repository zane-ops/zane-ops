import responses


# Direct response setup functions (for use with @responses.activate)


def mock_valid_registry_no_auth(url: str = "http://registry.example.com"):
    """Setup responses for a valid registry without auth."""
    responses.add(
        responses.GET,
        f"{url}/v2/",
        json={},
        status=200,
        headers={
            "Docker-Distribution-Api-Version": "registry/2.0",
            "Content-Type": "application/json",
        },
    )


def mock_valid_registry_with_basic_auth(
    url: str = "http://registry.example.com",
    username: str = "testuser",
    password: str = "testpass",
):
    """Setup responses for a valid registry with Basic auth."""
    import base64

    def basic_auth_callback(request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Basic "):
            # No auth provided - return 401
            return (
                401,
                {
                    "Docker-Distribution-Api-Version": "registry/2.0",
                    "WWW-Authenticate": 'Basic realm="Registry Realm"',
                    "Content-Type": "application/json",
                },
                '{"errors": [{"code": "UNAUTHORIZED"}]}',
            )

        # Decode and validate credentials
        try:
            encoded_credentials = auth_header.replace("Basic ", "")
            decoded = base64.b64decode(encoded_credentials).decode("utf-8")
            provided_user, provided_pass = decoded.split(":", 1)

            if provided_user == username and provided_pass == password:
                # Correct credentials - return 200
                return (
                    200,
                    {
                        "Docker-Distribution-Api-Version": "registry/2.0",
                        "Content-Type": "application/json",
                    },
                    "{}",
                )
            else:
                # Invalid credentials - return 401
                return (
                    401,
                    {
                        "Docker-Distribution-Api-Version": "registry/2.0",
                        "WWW-Authenticate": 'Basic realm="Registry Realm"',
                        "Content-Type": "application/json",
                    },
                    '{"errors": [{"code": "UNAUTHORIZED", "message": "Invalid credentials"}]}',
                )
        except Exception:
            # Malformed auth header - return 401
            return (
                401,
                {
                    "Docker-Distribution-Api-Version": "registry/2.0",
                    "WWW-Authenticate": 'Basic realm="Registry Realm"',
                    "Content-Type": "application/json",
                },
                '{"errors": [{"code": "UNAUTHORIZED"}]}',
            )

    responses.add_callback(
        responses.GET,
        f"{url}/v2/",
        callback=basic_auth_callback,
        content_type="application/json",
    )


def mock_valid_registry_with_bearer_auth(
    url: str = "http://registry.example.com",
    auth_url: str = "http://auth.example.com/token",
    service: str = "registry.example.com",
    token: str = "test-bearer-token",
    username: str = "testuser",
    password: str = "testpass",
):
    """Setup responses for a valid registry with Bearer auth."""
    import base64

    # Token endpoint callback - validates credentials
    def token_callback(request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Basic "):
            # No credentials provided - return unauthorized
            return (
                401,
                {"Content-Type": "application/json"},
                '{"errors": [{"code": "UNAUTHORIZED"}]}',
            )

        try:
            encoded_credentials = auth_header.replace("Basic ", "")
            decoded = base64.b64decode(encoded_credentials).decode("utf-8")
            provided_user, provided_pass = decoded.split(":", 1)

            if provided_user == username and provided_pass == password:
                # Valid credentials - return token
                return (
                    200,
                    {"Content-Type": "application/json"},
                    f'{{"token": "{token}", "access_token": "{token}"}}',
                )
            else:
                # Invalid credentials
                return (
                    401,
                    {"Content-Type": "application/json"},
                    '{"errors": [{"code": "UNAUTHORIZED", "message": "Invalid credentials"}]}',
                )
        except Exception:
            return (
                401,
                {"Content-Type": "application/json"},
                '{"errors": [{"code": "UNAUTHORIZED"}]}',
            )

    # Registry endpoint callback - validates bearer token
    def registry_callback(request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            # No token provided - return 401 with challenge
            return (
                401,
                {
                    "Docker-Distribution-Api-Version": "registry/2.0",
                    "WWW-Authenticate": f'Bearer realm="{auth_url}",service="{service}"',
                    "Content-Type": "application/json",
                },
                '{"errors": [{"code": "UNAUTHORIZED"}]}',
            )

        if auth_header == f"Bearer {token}":
            # Valid token - return 200
            return (
                200,
                {
                    "Docker-Distribution-Api-Version": "registry/2.0",
                    "Content-Type": "application/json",
                },
                "{}",
            )
        else:
            # Invalid token - return 401
            return (
                401,
                {
                    "Docker-Distribution-Api-Version": "registry/2.0",
                    "WWW-Authenticate": f'Bearer realm="{auth_url}",service="{service}",error="invalid_token"',
                    "Content-Type": "application/json",
                },
                '{"errors": [{"code": "UNAUTHORIZED", "message": "Invalid token"}]}',
            )

    responses.add_callback(
        responses.GET,
        auth_url,
        callback=token_callback,
        content_type="application/json",
    )

    responses.add_callback(
        responses.GET,
        f"{url}/v2/",
        callback=registry_callback,
        content_type="application/json",
    )


def mock_invalid_registry(url: str = "http://invalid.example.com"):
    """Setup responses for an invalid registry."""
    responses.add(
        responses.GET,
        f"{url}/v2/",
        json={"message": "Not a registry"},
        status=200,
        headers={"Content-Type": "application/json"},
    )
