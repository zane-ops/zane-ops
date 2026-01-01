from django.urls import re_path
from . import views

app_name = "compose"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"

urlpatterns = [
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/create?$",
        views.ComposeStackListAPIView.as_view(),
        name="stacks.create",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/?$",
        views.ComposeStackDetailsAPIView.as_view(),
        name="stacks.details",
    ),
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/(?P<slug>{DJANGO_SLUG_REGEX})/deploy?$",
        views.ComposeStackDeployAPIView.as_view(),
        name="stacks.deploy",
    ),
]
