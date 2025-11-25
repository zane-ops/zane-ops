from . import views
from .models import SharedRegistryCredentials, BuildRegistry
from django.urls import re_path

app_name = "container_registry"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(
        r"^credentials/?$",
        views.SharedRegistryCredentialsListAPIView.as_view(),
        name="credentials.list",
    ),
    re_path(
        rf"^credentials/(?P<id>{SharedRegistryCredentials.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.SharedRegistryCredentialsDetailsAPIView.as_view(),
        name="credentials.details",
    ),
    re_path(
        rf"^credentials/(?P<id>{SharedRegistryCredentials.ID_PREFIX}[a-zA-Z0-9]+)/test/?$",
        views.TestSharedRegistryCredentialsAPIView.as_view(),
        name="credentials.test",
    ),
    re_path(
        r"^build-registries/?$",
        views.BuildRegistryListCreateAPIView.as_view(),
        name="build_registries.list",
    ),
    re_path(
        rf"^build-registries/(?P<id>{BuildRegistry.ID_PREFIX}[a-zA-Z0-9]+)/?$",
        views.BuildRegistryDetailsAPIView.as_view(),
        name="build_registries.details",
    ),
]
