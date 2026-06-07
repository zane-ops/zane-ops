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
        r"^users/(?P<id>\d+)?$",
        views.InstanceUserDetailAPIView.as_view(),
        name="user.details",
    ),
    re_path(
        r"^workspaces/?$",
        views.ListWorkspacesAPIView.as_view(),
        name="workspaces.list",
    ),
]
