from django.urls import path, re_path

from . import views

app_name = "zane_api"

urlpatterns = [
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="auth_login"),
    re_path(r"^auth/me/?$", views.AuthedView.as_view(), name="auth_me"),
]
