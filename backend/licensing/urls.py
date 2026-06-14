from django.urls import re_path
from . import views

app_name = "licensing"

urlpatterns = [
    re_path(
        r"^list/?$",
        views.LicenseListAPIView.as_view(),
        name="licenses.list",
    ),
    re_path(
        r"^install/?$",
        views.LicenseInstallAPIView.as_view(),
        name="license.install",
    ),
    re_path(
        r"^uninstall/?$",
        views.LicenseUninstallAPIView.as_view(),
        name="license.uninstall",
    ),
]
