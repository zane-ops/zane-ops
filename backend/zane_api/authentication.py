from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.request import Request

from .models import WorkspaceApiToken


class WorkspaceTokenAuthentication(BaseAuthentication):
    """
    `Authorization: Bearer zn_tok_xxx_yyy` authentication for API tokens
    (plan §8).

    Returns `(token.created_by, token)` so `request.user` is the person who
    created the token and `request.auth` is the token itself — this keeps the
    ~119 `request.user` call sites unchanged. `request.workspace` is set from
    the token and the session is ignored entirely.

    Header parsing is deliberately forgiving: anything that is not a well-formed
    `Bearer` header returns `None` so the other authenticators get a turn. Only a
    genuine `Bearer` header carrying a bad value raises `AuthenticationFailed`.
    """

    keyword = b"bearer"

    def authenticate(self, request: Request):
        header = get_authorization_header(request).split()

        if not header or header[0].lower() != self.keyword:
            return None

        if len(header) == 1:
            raise exceptions.AuthenticationFailed(
                "Invalid bearer header. No credentials provided."
            )
        if len(header) > 2:
            raise exceptions.AuthenticationFailed(
                "Invalid bearer header. Token string should not contain spaces."
            )

        try:
            raw = header[1].decode()
        except UnicodeError:
            raise exceptions.AuthenticationFailed(
                "Invalid bearer header. Token string should not contain invalid characters."
            )

        return self.authenticate_credentials(raw)

    def authenticate_credentials(self, raw: str):
        token: WorkspaceApiToken | None = WorkspaceApiToken.authenticate(raw)

        if token is None:
            raise exceptions.AuthenticationFailed("Invalid or unknown API token.")

        if token.is_revoked:
            raise exceptions.AuthenticationFailed("This API token has been revoked.")

        if token.is_expired:
            raise exceptions.AuthenticationFailed("This API token has expired.")

        token.touch_last_used()

        # `HasWorkspace` sees `request.auth` is a token and sets
        # `request.workspace` / `request.access` from it, ignoring the session.
        return (token.created_by, token)

    def authenticate_header(self, request):  # type: ignore
        return 'Bearer realm="api"'


class WorkspaceTokenAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "zane_api.authentication.WorkspaceTokenAuthentication"
    name = "workspaceApiToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "zn_tok_<id>_<secret>",
            "description": (
                "Workspace API token (plan §8). Send as "
                "`Authorization: Bearer zn_tok_...`."
            ),
        }
