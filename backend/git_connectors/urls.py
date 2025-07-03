from . import views
from django.urls import re_path
from zane_api.models import GitApp, GithubApp

app_name = "git_connectors"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^github/setup/?$",
        views.SetupCreateGithubAppAPIView.as_view(),
        name="github.setup",
    ),
    re_path(
        rf"^github/(?P<id>{GithubApp.ID_PREFIX}[a-zA-Z0-9]+)/repositories/?$",
        views.ListGithubRepositoriesAPIView.as_view(),
        name="github.list_repositories",
    ),
    re_path(
        rf"^github/(?P<id>{GithubApp.ID_PREFIX}[a-zA-Z0-9]+)/rename/?$",
        views.RenameGithubAppAPIView.as_view(),
        name="github.rename",
    ),
    re_path(
        r"^list/?$",
        views.ListGitAppsAPIView.as_view(),
        name="git_apps.list",
    ),
    re_path(
        rf"^delete/(?P<id>{GitApp.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.DeleteGitAppAPIView.as_view(),
        name="git_apps.delete",
    ),
    # re_path(r"^github/webhook?$", views.SSHKeyListAPIView.as_view(), name="github.webhook"),
]
