# type: ignore
from django.urls import re_path
from . import consumers

DJANGO_SLUG_REGEX = r"[-_\w]+"  # => \w is alphanumeric chars (lowercase + uppercase)
websocket_urlpatterns = [
    re_path(
        rf"ws/deployment-terminal/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})"
        r"/(?P<deployment_hash>[a-zA-Z0-9-_]+)/(?P<container_id>([\w])+)/?$",
        consumers.DeploymentContainerTerminalRelay.as_asgi(),
    ),
    re_path(
        rf"ws/compose-stack-terminal/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})"
        rf"/(?P<stack_slug>{DJANGO_SLUG_REGEX})"
        r"/(?P<service_name>([^\s])+)/(?P<container_id>([\w])+)/?$",
        consumers.ComposeStackTerminalRelay.as_asgi(),
    ),
    re_path(
        r"ws/server-ssh/(?P<node_id>[a-zA-Z0-9-_]+)/(?P<key_id>[0-9]+)/?$",
        consumers.ServerTerminalConsumer.as_asgi(),
    ),
]


worker_urlpatterns = [
    re_path(
        r"ws/container-terminal/(?P<container_id>([\w])+)/?$",
        consumers.ContainerTerminalConsumer.as_asgi(),
    ),
]
