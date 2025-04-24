# webshell/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/webshell/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        consumers.WebShellConsumer.as_asgi(),
    ),
]
