from . import views
from django.urls import re_path
from zane_api.models import GitApp, GithubApp

app_name = "git_connectors"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^list/?$",
        views.ListGitAppsAPIView.as_view(),
        name="git_apps.list",
    ),
    re_path(
        rf"^(?P<id>{GitApp.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.GitAppDetailsAPIView.as_view(),
        name="git_apps.details",
    ),
    re_path(
        r"^github/setup/?$",
        views.SetupCreateGithubAppAPIView.as_view(),
        name="github.setup",
    ),
    re_path(
        rf"^github/(?P<id>{GithubApp.ID_PREFIX}[a-zA-Z0-9]+)/test/?$",
        views.TestGithubAppAPIView.as_view(),
        name="github.test",
    ),
    re_path(
        rf"^github/(?P<id>{GithubApp.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.GithubAppDetailsAPIView.as_view(),
        name="github.details",
    ),
    re_path(
        rf"^github/(?P<id>{GithubApp.ID_PREFIX}[a-zA-Z0-9]+)/repositories/?$",
        views.ListGithubRepositoriesAPIView.as_view(),
        name="github.list_repositories",
    ),
    re_path(
        r"^github/webhook?$",
        views.GithubWebhookAPIView.as_view(),
        name="github.webhook",
    ),
]
