from . import views
from django.urls import re_path
from zane_api.models import GitApp

app_name = "git_connectors"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^github/setup/?$",
        views.SetupCreateGithubConnectorAPIView.as_view(),
        name="github.setup",
    ),
    re_path(
        r"^list/?$",
        views.ListGitAppsAPIView.as_view(),
        name="git_apps.list",
    ),
    re_path(
        rf"^delete/{GitApp.ID_PREFIX}[a-zA-Z0-9]+/?$",
        views.DeleteGitAppAPIView.as_view(),
        name="git_apps.delete",
    ),
    # re_path(
    #     r"^github/setup/?$",
    #     views.SetupCreateGithubConnectorAPIView.as_view(),
    #     name="github.setup",
    # ),
    # re_path(r"^github/webhook?$", views.SSHKeyListAPIView.as_view(), name="github.webhook"),
]
