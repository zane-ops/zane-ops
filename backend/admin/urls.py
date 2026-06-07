from django.urls import re_path
from . import views

app_name = "admin"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"

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
        r"^users/(?P<id>\d+)/generate-password-reset-code/?$",
        views.GeneratePasswordTokenAPIView.as_view(),
        name="user.generate_password_reset",
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
]
