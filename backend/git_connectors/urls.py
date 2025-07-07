from . import views
from django.urls import re_path
from zane_api.models import GitApp, GitHubApp, GitlabApp

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
        views.SetupGithubAppAPIView.as_view(),
        name="github.setup",
    ),
    re_path(
        rf"^github/(?P<id>{GitHubApp.ID_PREFIX}[a-zA-Z0-9]+)/test/?$",
        views.TestGithubAppAPIView.as_view(),
        name="github.test",
    ),
    re_path(
        rf"^github/(?P<id>{GitHubApp.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.GithubAppDetailsAPIView.as_view(),
        name="github.details",
    ),
    re_path(
        rf"^github/(?P<id>{GitHubApp.ID_PREFIX}[a-zA-Z0-9]+)/repositories/?$",
        views.ListGithubRepositoriesAPIView.as_view(),
        name="github.list_repositories",
    ),
    re_path(
        r"^github/webhook?$",
        views.GithubWebhookAPIView.as_view(),
        name="github.webhook",
    ),
    re_path(
        r"^gitlab/create/?$",
        views.CreateGitlabAppAPIView.as_view(),
        name="gitlab.create",
    ),
    re_path(
        r"^gitlab/setup/?$",
        views.SetupGitlabAppAPIView.as_view(),
        name="gitlab.setup",
    ),
    re_path(
        rf"^gitlab/(?P<id>{GitlabApp.ID_PREFIX}[a-zA-Z0-9]+)/test/?$",
        views.TestGitlabAppAPIView.as_view(),
        name="gitlab.test",
    ),
]
