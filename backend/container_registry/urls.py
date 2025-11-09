from . import views
from .models import ContainerRegistryCredentials
from django.urls import re_path

app_name = "container_registry"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^credentials/?$",
        views.ContainerRegistryCredentialsListAPIView.as_view(),
        name="credentials.list",
    ),
    re_path(
        rf"^credentials/(?P<id>{ContainerRegistryCredentials.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.ContainerRegistryCredentialsDetailsAPIView.as_view(),
        name="credentials.details",
    ),
    re_path(
        rf"^credentials/(?P<id>{ContainerRegistryCredentials.ID_PREFIX}[a-zA-Z0-9]+)/test/?$",
        views.TestContainerRegistryCredentialsAPIView.as_view(),
        name="credentials.test",
    ),
    re_path(
        r"^build-registries/?$",
        views.BuildRegistryListCreateAPIView.as_view(),
        name="build_registries.list",
    ),
]
