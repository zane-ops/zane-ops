from django.urls import re_path
from . import consumers

DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
websocket_urlpatterns = [
    re_path(
        rf"ws/deployment-terminal/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        consumers.DeploymentTerminalConsumer.as_asgi(),
    ),
]
