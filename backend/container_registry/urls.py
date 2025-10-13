from . import views
from django.urls import re_path

app_name = "container_registry"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^credentials/?$",
        views.ContainerRegistryCredentialsListAPIView.as_view(),
        name="credentials.list",
    ),
]
