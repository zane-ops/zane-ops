from django.urls import re_path

from . import views

app_name = "swarm"

urlpatterns = [
    re_path(
        r"^nodes/?$",
        views.SwarmNodeListAPIView.as_view(),
        name="nodes.list",
    ),
    re_path(
        r"^nodes/main/?$",
        views.MainSwarmNodeAPIView.as_view(),
        name="node.main",
    ),
    re_path(
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/?$",
        views.SwarmNodeDetailsAPIView.as_view(),
        name="node.detail",
    ),
    re_path(
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/provision/?$",
        views.ProvisionSwarmNodeAPIView.as_view(),
        name="node.provision",
    ),
    re_path(
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/deprovision/?$",
        views.DeprovisionSwarmNodeAPIView.as_view(),
        name="node.deprovision",
    ),
    re_path(
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/build-logs/?$",
        views.SwarmNodeBuildLogsAPIView.as_view(),
        name="node.build_logs",
    ),
    re_path(
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/ssh-keys/?$",
        views.SwarmNodeSSHKeysAPIView.as_view(),
        name="node.ssh_keys",
    ),
    re_path(
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/ssh-keys/(?P<key_id>[0-9]+)/?$",
        views.SwarmNodeSSHKeyDetailsAPIView.as_view(),
        name="node.ssh_keys.details",
    ),
]
