from django.urls import re_path
from . import views

app_name = "compose"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"

urlpatterns = [
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ComposeStackListAPIView.as_view(),
        name="stacks.list",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/create/?$",
        views.ComposeStackCreateAPIView.as_view(),
        name="stacks.create",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/create-from-dokploy/base-64/?$",
        views.ComposeStackCreateFromDokployBase64APIView.as_view(),
        name="stacks.create_from_dokploy.base64",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/create-from-dokploy/object/?$",
        views.ComposeStackCreateFromDokployObjectAPIView.as_view(),
        name="stacks.create_from_dokploy.object",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/?$",
        views.ComposeStackDetailsAPIView.as_view(),
        name="stacks.details",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/request-changes/?$",
        views.ComposeStackRequestChanges.as_view(),
        name="stacks.request_changes",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/deploy/?$",
        views.ComposeStackDeployAPIView.as_view(),
        name="stacks.deploy",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/deploy/(?P<hash>[a-zA-Z0-9-_]+)/?$",
        views.ComposeStackReDeployAPIView.as_view(),
        name="stacks.redeploy",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/archive/?$",
        views.ComposeStackArchiveAPIView.as_view(),
        name="stacks.archive",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/toggle/?$",
        views.ToggleComposeStackAPIView.as_view(),
        name="stacks.toggle",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/(?P<hash>[a-zA-Z0-9-_]+)/?$",
        views.ComposeStackDeploymentDetailsAPIView.as_view(),
        name="stacks.deployments.details",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/(?P<hash>[a-zA-Z0-9-_]+)/cancel/?$",
        views.CancelComposeStackDeploymentAPIView.as_view(),
        name="stacks.deployments.cancel",
    ),
]
