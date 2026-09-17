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
        r"^nodes/(?P<id>[a-zA-Z0-9_]+)/?$",
        views.SwarmNodeDetailsAPIView.as_view(),
        name="node.detail",
    ),
]
