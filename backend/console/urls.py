from django.urls import re_path
from zane_api.urls import UUID_REGEX
from . import views

app_name = "console"

urlpatterns = [
    re_path(
        r"^users/?$",
        views.ListInstanceUsersAPIView.as_view(),
        name="users.list",
    ),
    re_path(
        r"^users/(?P<id>\d+)/?$",
        views.InstanceUserDetailAPIView.as_view(),
        name="user.details",
    ),
    re_path(
        r"^users/(?P<id>\d+)/generate-password-token/?$",
        views.GeneratePasswordTokenAPIView.as_view(),
        name="user.generate_password_reset",
    ),
    re_path(
        r"^password-tokens/?$",
        views.PasswordTokenListAPIView.as_view(),
        name="password_tokens.list",
    ),
    re_path(
        r"^password-tokens/(?P<id>\d+)?$",
        views.PasswordTokenDetailAPIView.as_view(),
        name="password_token.detail",
    ),
    re_path(
        r"^workspaces/?$",
        views.ListWorkspacesAPIView.as_view(),
        name="workspaces.list",
    ),
    re_path(
        r"^workspaces/(?P<id>[a-zA-Z0-9_]+)/?$",
        views.WorkspaceDetailAPIView.as_view(),
        name="workspace.detail",
    ),
    re_path(
        r"^workspaces/(?P<id>[a-zA-Z0-9_]+)/transfer-ownership/?$",
        views.WorkspaceTransferOwnershipAPIView.as_view(),
        name="workspace.transfer_ownership",
    ),
    re_path(
        r"^system-settings/?$",
        views.SystemSettingsAPIView.as_view(),
        name="system.settings",
    ),
    re_path(
        r"^proxy/http-logs/?$",
        views.ProxyHttpLogsAPIView.as_view(),
        name="proxy.http_logs",
    ),
    re_path(
        r"^proxy/http-logs/fields/?$",
        views.ProxyHttpLogsFieldsAPIView.as_view(),
        name="proxy.http_logs.fields",
    ),
    re_path(
        rf"^proxy/http-logs/(?P<request_uuid>{UUID_REGEX})/?$",
        views.SingleProxyHttpLogAPIView.as_view(),
        name="proxy.http_logs.single",
    ),
    re_path(
        r"^proxy/logs/?$",
        views.ProxyLogsAPIView.as_view(),
        name="proxy.logs",
    ),
]
