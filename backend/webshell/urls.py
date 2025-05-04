from . import views
from django.urls import re_path

app_name = "webshell"

urlpatterns = [
    re_path(r"^ssh_keys/?$", views.SSHKeyListAPIView.as_view(), name="ssh.keys")
]
