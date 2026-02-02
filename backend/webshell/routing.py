# type: ignore
from django.urls import re_path
from . import consumers

DJANGO_SLUG_REGEX = r"[-_\w]+"  # => \w is alphanumeric chars (lowercase + uppercase)
websocket_urlpatterns = [
    re_path(
        rf"ws/deployment-terminal/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        consumers.DeploymentTerminalConsumer.as_asgi(),
    ),
    re_path(
        rf"ws/compose-stack-terminal/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})"
        rf"/(?P<stack_slug>{DJANGO_SLUG_REGEX})"
        r"/(?P<service_name>([^\s])+)/(?P<task_id>([\w])+)/?$",
        consumers.ComposeStackTerminalConsumer.as_asgi(),
    ),
    re_path(
        rf"ws/server-ssh/(?P<slug>{DJANGO_SLUG_REGEX})/?$",
        consumers.ServerTerminalConsumer.as_asgi(),
    ),
]
