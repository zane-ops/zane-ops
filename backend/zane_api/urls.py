from django.urls import re_path

from . import views

app_name = "zane_api"

urlpatterns = [
    re_path(r"^auth/me/?$", views.AuthedView.as_view(), name="auth.me"),
    re_path(
        r"^auth/me/with-token/?$",
        views.TokenAuthedView.as_view(),
        name="auth.me.with_token",
    ),
    re_path(r"^auth/logout/?$", views.AuthLogoutView.as_view(), name="auth.logout"),
    re_path(r"^csrf/?$", views.CSRFCookieView.as_view(), name="csrf"),
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="auth.login"),
    re_path(r"^projects/?$", views.ProjectsListAPIView.as_view(), name="projects.list"),
    re_path(
        r"^archived-projects/?$",
        views.ArchivedProjectsListAPIView.as_view(),
        name="projects.archived.list",
    ),
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
    re_path(
        r"^docker/image-search/?$",
        views.DockerImageSearchView.as_view(),
        name="docker.image_search",
    ),
    re_path(r"^docker/login/?$", views.DockerLoginView.as_view(), name="docker.login"),
    re_path(
        r"^docker/check-port/?$",
        views.DockerPortCheckView.as_view(),
        name="docker.check_port_mapping",
    ),
    re_path(
        r"^volumes/(?P<volume_id>[a-zA-Z0-9_]+)/size/?$",
        views.VolumeGetSizeView.as_view(),
        name="volume.size",
    ),
    re_path(
        r"^projects/(?P<project_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/create-service/docker/?$",
        views.CreateDockerServiceAPIView.as_view(),
        name="services.docker.create",
    ),
    re_path(
        r"^projects/(?P<project_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/update-service/docker"
        r"/(?P<service_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/?$",
        views.DockerServiceDeploymentChangesAPIView.as_view(),
        name="services.docker.deployment_changes",
    ),
    re_path(
        r"^projects/(?P<project_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/archive-service/docker"
        r"/(?P<service_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/?$",
        views.ArchiveDockerServiceAPIView.as_view(),
        name="services.docker.archive",
    ),
    re_path(
        r"^projects/(?P<project_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/service-details/docker"
        r"/(?P<service_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/?$",
        views.GetDockerServiceAPIView.as_view(),
        name="services.docker.details",
    ),
    re_path(
        r"^projects/(?P<project_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/service-details/docker"
        r"/(?P<service_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/deployments/?$",
        views.DockerServiceDeploymentsAPIView.as_view(),
        name="services.docker.deployments_list",
    ),
    re_path(
        r"^projects/(?P<project_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/service-details/docker"
        r"/(?P<service_slug>[a-z0-9]+(?:-[a-z0-9]+)*)/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.DockerServiceDeploymentSingleAPIView.as_view(),
        name="services.docker.deployment_single",
    ),
]
