from . import views
from django.urls import re_path

app_name = "webshell"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
urlpatterns = [
    re_path(r"^ssh-keys/?$", views.SSHKeyListAPIView.as_view(), name="ssh.keys"),
    re_path(
        rf"^ssh-keys/(?P<slug>{DJANGO_SLUG_REGEX})/?$",
        views.SSHKeyDetailsAPIView.as_view(),
        name="ssh.keys.details",
    ),
]
