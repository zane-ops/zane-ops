from django.urls import re_path

from . import views

app_name = "zane_api"

urlpatterns = [
    re_path(r"^auth/me/?$", views.AuthedView.as_view(), name="auth.me"),
    re_path(r"^auth/logout/?$", views.AuthLogoutView.as_view(), name="auth.logout"),
    re_path(r"^csrf/?$", views.CSRFCookieView.as_view(), name="csrf"),
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="auth.login"),
]
