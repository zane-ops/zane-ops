from django.conf import settings
from django.urls import re_path

from . import views

app_name = "zane_api"

DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
UUID_REGEX = r"[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}"

urlpatterns = [
    re_path(r"^auth/me/?$", views.AuthedView.as_view(), name="auth.me"),
    re_path(
        r"^auth/me/with-token/?$",
        views.TokenAuthedView.as_view(),
        name="auth.me.with_token",
    ),
    re_path(r"^auth/logout/?$", views.AuthLogoutView.as_view(), name="auth.logout"),
    re_path(r"^csrf/?$", views.CSRFCookieView.as_view(), name="csrf"),
    re_path(r"^ping/?$", views.PINGView.as_view(), name="ping"),
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="auth.login"),
    re_path(r"^projects/?$", views.ProjectsListAPIView.as_view(), name="projects.list"),
    re_path(
        r"^archived-projects/?$",
        views.ArchivedProjectsListAPIView.as_view(),
        name="projects.archived.list",
    ),
    re_path(
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/$",
        views.ProjectDetailsView.as_view(),
        name="projects.details",
    ),
    re_path(
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/service-list/$",
        views.ProjectServiceListView.as_view(),
        name="projects.service_list",
    ),
    re_path(
        r"^docker/image-search/?$",
        views.DockerImageSearchView.as_view(),
        name="docker.image_search",
    ),
    re_path(
        r"^settings/?$",
        views.SettingsView.as_view(),
        name="settings",
    ),
    re_path(
        r"^server/resource-limits/?$",
        views.ResourceLimitsView.as_view(),
        name="server.resource_limits",
    ),
    re_path(
        r"^docker/image-search/?$",
        views.DockerImageSearchView.as_view(),
        name="docker.image_search",
    ),
    re_path(
        r"^docker/check-port/?$",
        views.DockerPortCheckView.as_view(),
        name="docker.check_port_mapping",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/create-service/docker/?$",
        views.CreateDockerServiceAPIView.as_view(),
        name="services.docker.create",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/request-service-changes/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.RequestDockerServiceDeploymentChangesAPIView.as_view(),
        name="services.docker.request_deployment_changes",
    ),
    re_path(
        r"^search-resources/?$",
        views.ResouceSearchAPIView.as_view(),
        name="resources.search",
    ),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(
            rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/request-service-changes/docker"
            rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/_bulk/?$",
            views.BulkRequestDockerServiceDeploymentChangesAPIView.as_view(),
        ),
    ]


urlpatterns += [
    re_path(
        r"^_proxy/check-certiticates/?$",
        views.CheckCertificatesAPIView.as_view(),
        name="proxy.check_certificates",
    ),
    re_path(
        "^logs/ingest/?$",
        views.LogIngestAPIView.as_view(),
        name="logs.ingest",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/cancel-service-changes/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<change_id>[a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)*)/?$",
        views.CancelDockerServiceDeploymentChangesAPIView.as_view(),
        name="services.docker.cancel_deployment_changes",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/deploy-service/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ApplyDockerServiceDeploymentChangesAPIView.as_view(),
        name="services.docker.deploy_service",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/deploy-service/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.RedeployDockerServiceAPIView.as_view(),
        name="services.docker.redeploy_service",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/cancel-deployment/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.CancelDockerServiceDeploymentAPIView.as_view(),
        name="services.docker.cancel_deployment",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/archive-service/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ArchiveDockerServiceAPIView.as_view(),
        name="services.docker.archive",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/toggle-service/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ToggleDockerServiceAPIView.as_view(),
        name="services.docker.toggle",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.DockerServiceDetailsAPIView.as_view(),
        name="services.docker.details",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/?$",
        views.DockerServiceDeploymentsAPIView.as_view(),
        name="services.docker.deployments_list",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.DockerServiceDeploymentSingleAPIView.as_view(),
        name="services.docker.deployment_single",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/http-logs/?$",
        views.DockerServiceHttpLogsAPIView.as_view(),
        name="services.docker.http_logs",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/http-logs"
        rf"/(?P<request_uuid>{UUID_REGEX})/?$",
        views.DockerServiceSingleHttpLogAPIView.as_view(),
        name="services.docker.http_logs.single",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/http-logs/fields/?$",
        views.DockerServiceHttpLogsFieldsAPIView.as_view(),
        name="services.docker.http_logs.fields",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/logs/?$",
        views.DockerServiceDeploymentLogsAPIView.as_view(),
        name="services.docker.deployment_logs",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/http-logs/?$",
        views.DockerServiceDeploymentHttpLogsAPIView.as_view(),
        name="services.docker.deployment_http_logs",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/http-logs/fields/?$",
        views.DockerServiceDeploymentHttpLogsFieldsAPIView.as_view(),
        name="services.docker.deployment_http_logs.fields",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/http-logs"
        rf"/(?P<request_uuid>{UUID_REGEX})/?$",
        views.DockerServiceDeploymentSingleHttpLogAPIView.as_view(),
        name="services.docker.deployment_http_logs.single",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/service-details/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/regenerate-deploy-token/?$",
        views.RegenerateServiceDeployTokenAPIView.as_view(),
        name="services.docker.regenerate_deploy_token",
    ),
    re_path(
        rf"^deploy-service/docker/(?P<deploy_token>[a-zA-Z0-9-_]+)?$",
        views.WebhookDeployServiceAPIView.as_view(),
        name="services.docker.webhook_deploy",
    ),
]
