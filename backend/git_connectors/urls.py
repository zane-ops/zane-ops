from . import views
from django.urls import re_path

app_name = "git_connectors"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^github/setup?$",
        views.SetupCreateGithubConnectorAPIView.as_view(),
        name="github.create",
    ),
    # re_path(r"^github/setup?$", views.SSHKeyListAPIView.as_view(), name="github.setup"),
    # re_path(r"^github/webhook?$", views.SSHKeyListAPIView.as_view(), name="github.webhook"),
    # re_path(
    #     rf"^ssh-keys/(?P<slug>{DJANGO_SLUG_REGEX})/?$",
    #     views.SSHKeyDetailsAPIView.as_view(),
    #     name="ssh.keys.details",
    # ),
]
