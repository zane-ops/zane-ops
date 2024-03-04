from django.urls import re_path

from . import views

app_name = "zane_api"

urlpatterns = [
    re_path(r"^auth/me/?$", views.AuthedView.as_view(), name="auth.me"),
    re_path(r"^auth/logout/?$", views.AuthLogoutView.as_view(), name="auth.logout"),
    re_path(r"^csrf/?$", views.CSRFCookieView.as_view(), name="csrf"),
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="auth.login"),
    re_path(r"^projects/?$", views.ProjectsListView.as_view(), name="projects.list"),
    re_path(
        r"^projects/(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)/$",
        views.ProjectDetailsView.as_view(),
        name="projects.details",
    ),
    re_path(
        r"^docker/image-search/?$",
        views.DockerImageSearchView.as_view(),
        name="docker.image_search",
    ),
    re_path(r"^docker/login/?$", views.DockerLoginView.as_view(), name="docker.login"),
    re_path(r"^domain/root/?$", views.GetRootDomainView.as_view(), name="domain.root"),
]
