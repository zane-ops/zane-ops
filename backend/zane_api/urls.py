from django.conf import settings
from django.urls import re_path
from typing import List

from . import views

app_name = "zane_api"

# Define constants for regular expressions
DJANGO_SLUG_REGEX = r"[-a-zA-Z0-9_]+"
UUID_REGEX = r"[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}"

# Improved readability by breaking long regular expression lines
PROJECT_SLUG_REGEX = rf"projects/(?P<project_slug>{DJANGO_SLUG_REGEX})"
SERVICE_SLUG_REGEX = rf"docker/(?P<service_slug>{DJANGO_SLUG_REGEX})"
DEPLOYMENT_HASH_REGEX = r"(?P<deployment_hash>[a-zA-Z0-9-_]+)"
REQUEST_UUID_REGEX = rf"(?P<request_uuid>{UUID_REGEX})"
CHANGE_ID_REGEX = r"(?P<change_id>[a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)*)"

# Define a list of URL patterns
urlpatterns: List[Any] = [
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
        rf"^{PROJECT_SLUG_REGEX}/create-service/{SERVICE_SLUG_REGEX.split('/')[0]}/?$",
        views.CreateDockerServiceAPIView.as_view(),
        name="services.docker.create",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/request-service-changes/{SERVICE_SLUG_REGEX}/?$",
        views.RequestDockerServiceDeploymentChangesAPIView.as_view(),
        name="services.docker.request_deployment_changes",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/request-env-changes/{SERVICE_SLUG_REGEX}/?$",
        views.RequestDockerServiceEnvChangesAPIView.as_view(),
        name="services.docker.request_env_changes",
    ),
    re_path(
        r"^search-resources/?$",
        views.ResouceSearchAPIView.as_view(),
        name="resources.search",
    ),
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
        rf"^{PROJECT_SLUG_REGEX}/cancel-service-changes/{SERVICE_SLUG_REGEX}/{CHANGE_ID_REGEX}/?$",
        views.CancelDockerServiceDeploymentChangesAPIView.as_view(),
        name="services.docker.cancel_deployment_changes",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/deploy-service/{SERVICE_SLUG_REGEX}/?$",
        views.DeployDockerServiceAPIView.as_view(),
        name="services.docker.deploy_service",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/deploy-service/{SERVICE_SLUG_REGEX}/{DEPLOYMENT_HASH_REGEX}/?$",
        views.RedeployDockerServiceAPIView.as_view(),
        name="services.docker.redeploy_service",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/cancel-deployment/{SERVICE_SLUG_REGEX}/{DEPLOYMENT_HASH_REGEX}/?$",
        views.CancelDockerServiceDeploymentAPIView.as_view(),
        name="services.docker.cancel_deployment",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/archive-service/{SERVICE_SLUG_REGEX}/?$",
        views.ArchiveDockerServiceAPIView.as_view(),
        name="services.docker.archive",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/toggle-service/{SERVICE_SLUG_REGEX}/?$",
        views.ToggleDockerServiceAPIView.as_view(),
        name="services.docker.toggle",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/?$",
        views.DockerServiceDetailsAPIView.as_view(),
        name="services.docker.details",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/?$",
        views.DockerServiceDeploymentsAPIView.as_view(),
        name="services.docker.deployments_list",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/{DEPLOYMENT_HASH_REGEX}/?$",
        views.DockerServiceDeploymentSingleAPIView.as_view(),
        name="services.docker.deployment_single",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/http-logs/?$",
        views.DockerServiceHttpLogsAPIView.as_view(),
        name="services.docker.http_logs",
    ),
     re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/metrics/?$",
        views.DockerServiceMetricsAPIView.as_view(),
        name="services.docker.metrics",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/http-logs/{REQUEST_UUID_REGEX}/?$",
        views.DockerServiceSingleHttpLogAPIView.as_view(),
        name="services.docker.http_logs.single",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/http-logs/fields/?$",
        views.DockerServiceHttpLogsFieldsAPIView.as_view(),
        name="services.docker.http_logs.fields",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/{DEPLOYMENT_HASH_REGEX}/logs/?$",
        views.DockerServiceDeploymentLogsAPIView.as_view(),
        name="services.docker.deployment_logs",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/{DEPLOYMENT_HASH_REGEX}/http-logs/?$",
        views.DockerServiceDeploymentHttpLogsAPIView.as_view(),
        name="services.docker.deployment_http_logs",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/{DEPLOYMENT_HASH_REGEX}/http-logs/fields/?$",
        views.DockerServiceDeploymentHttpLogsFieldsAPIView.as_view(),
        name="services.docker.deployment_http_logs.fields",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/{DEPLOYMENT_HASH_REGEX}/http-logs/{REQUEST_UUID_REGEX}/?$",
        views.DockerServiceDeploymentSingleHttpLogAPIView.as_view(),
        name="services.docker.deployment_http_logs.single",
    ),
        re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/deployments/{DEPLOYMENT_HASH_REGEX}/metrics/?$",
        views.DockerServiceMetricsAPIView.as_view(),
        name="services.docker.deployment_metrics",
    ),
    re_path(
        rf"^{PROJECT_SLUG_REGEX}/service-details/{SERVICE_SLUG_REGEX}/regenerate-deploy-token/?$",
        views.RegenerateServiceDeployTokenAPIView.as_view(),
        name="services.docker.regenerate_deploy_token",
    ),
    re_path(
        rf"^deploy-service/{SERVICE_SLUG_REGEX.split('/')[0]}/(?P<deploy_token>[a-zA-Z0-9-_]+)?$",
        views.WebhookDeployServiceAPIView.as_view(),
        name="services.docker.webhook_deploy",
    ),
    re_path(
        r"^auth/check-user-existence/?$",
        views.CheckUserExistenceView.as_view(),
        name="auth.check_user_existence",
    ),
    re_path(
        r"^auth/create-initial-user/?$",
        views.CreateUserView.as_view(),
        name="auth.create_initial_user",
    ),
]
