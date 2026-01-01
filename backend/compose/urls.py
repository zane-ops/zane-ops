from django.urls import re_path
from . import views

app_name = "compose"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"

urlpatterns = [
    re_path(
        rf"^stacks/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ComposeStackListAPIView.as_view(),
        name="stacks.create",
    ),
]
