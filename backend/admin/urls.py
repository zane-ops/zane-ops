from django.urls import re_path
from . import views

app_name = "admin"
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"

urlpatterns = [
    re_path(
        r"^users/?$",
        views.ListInstanceUsersAPIView.as_view(),
        name="stacks.list",
    )
]
