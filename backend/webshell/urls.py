from . import views
from django.urls import re_path

app_name = "webshell"

urlpatterns = [
    re_path(r"^ssh-keys/?$", views.SSHKeyListAPIView.as_view(), name="ssh.keys"),
    re_path(
        r"^ssh-keys/(?P<id>\d+)/?$",
        views.SSHKeyDetailsAPIView.as_view(),
        name="ssh.keys.details",
    ),
]
