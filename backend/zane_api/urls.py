from django.conf import settings
from django.urls import re_path
from rest_framework import routers

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
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/?$",
        views.ProjectDetailsView.as_view(),
        name="projects.details",
    ),
    re_path(
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/create-environment/?$",
        views.CreateEnviromentAPIView.as_view(),
        name="projects.environment.create",
    ),
    re_path(
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/clone-environment/(?P<env_slug>{DJANGO_SLUG_REGEX})/?$",
        views.CloneEnviromentAPIView.as_view(),
        name="projects.environment.clone",
    ),
    re_path(
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/environment-details/(?P<env_slug>{DJANGO_SLUG_REGEX})/?$",
        views.EnvironmentDetailsAPIView.as_view(),
        name="projects.environment.details",
    ),
    re_path(
        rf"^projects/(?P<slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-list/?$",
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
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/create-service/docker/?$",
        views.CreateDockerServiceAPIView.as_view(),
        name="services.docker.create",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/create-service/git/?$",
        views.CreateGitServiceAPIView.as_view(),
        name="services.git.create",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/request-service-changes"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.RequestServiceChangesAPIView.as_view(),
        name="services.request_deployment_changes",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/request-env-changes"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.RequestServiceEnvChangesAPIView.as_view(),
        name="services.request_env_changes",
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
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/cancel-service-changes"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<change_id>[a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)*)/?$",
        views.CancelServiceDeploymentChangesAPIView.as_view(),
        name="services.cancel_deployment_changes",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/deploy-service/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.DeployDockerServiceAPIView.as_view(),
        name="services.docker.deploy_service",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/deploy-service/git"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.DeployGitServiceAPIView.as_view(),
        name="services.git.deploy_service",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/redeploy-service/docker"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.RedeployDockerServiceAPIView.as_view(),
        name="services.docker.redeploy_service",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/redeploy-service/git"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.ReDeployGitServiceAPIView.as_view(),
        name="services.git.redeploy_service",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/cancel-deployment"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.CancelServiceDeploymentAPIView.as_view(),
        name="services.cancel_deployment",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/archive-service/docker/"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ArchiveDockerServiceAPIView.as_view(),
        name="services.docker.archive",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/toggle-service"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ToggleServiceAPIView.as_view(),
        name="services.docker.toggle",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/bulk-toggle-services/?$",
        views.BulkToggleServicesAPIView.as_view(),
        name="services.bulk_toggle_state",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/?$",
        views.ServiceDetailsAPIView.as_view(),
        name="services.details",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/?$",
        views.ServiceDeploymentsAPIView.as_view(),
        name="services.deployments_list",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/?$",
        views.ServiceDeploymentSingleAPIView.as_view(),
        name="services.deployment_single",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/http-logs/?$",
        views.ServiceHttpLogsAPIView.as_view(),
        name="services.http_logs",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/metrics/?$",
        views.ServiceMetricsAPIView.as_view(),
        name="services.metrics",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/http-logs"
        rf"/(?P<request_uuid>{UUID_REGEX})/?$",
        views.ServiceSingleHttpLogAPIView.as_view(),
        name="services.http_logs.single",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/http-logs/fields/?$",
        views.ServiceHttpLogsFieldsAPIView.as_view(),
        name="services.http_logs.fields",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/logs/?$",
        views.ServiceDeploymentLogsAPIView.as_view(),
        name="services.deployment_logs",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/http-logs/?$",
        views.ServiceDeploymentHttpLogsAPIView.as_view(),
        name="services.deployment_http_logs",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/http-logs/fields/?$",
        views.ServiceDeploymentHttpLogsFieldsAPIView.as_view(),
        name="services.deployment_http_logs.fields",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/http-logs"
        rf"/(?P<request_uuid>{UUID_REGEX})/?$",
        views.ServiceDeploymentSingleHttpLogAPIView.as_view(),
        name="services.deployment_http_logs.single",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/deployments/(?P<deployment_hash>[a-zA-Z0-9-_]+)/metrics/?$",
        views.ServiceMetricsAPIView.as_view(),
        name="services.deployment_metrics",
    ),
    re_path(
        rf"^projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/service-details"
        rf"/(?P<service_slug>{DJANGO_SLUG_REGEX})/regenerate-deploy-token/?$",
        views.RegenerateServiceDeployTokenAPIView.as_view(),
        name="services.regenerate_deploy_token",
    ),
    re_path(
        r"^deploy-service/docker/(?P<deploy_token>[a-zA-Z0-9-_]+)?$",
        views.WebhookDeployDockerServiceAPIView.as_view(),
        name="services.docker.webhook_deploy",
    ),
    re_path(
        r"^deploy-service/git/(?P<deploy_token>[a-zA-Z0-9-_]+)?$",
        views.WebhookDeployGitServiceAPIView.as_view(),
        name="services.git.webhook_deploy",
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
    re_path(
        r"^trigger-update/?$",
        views.TriggerUpdateView.as_view(),
        name="app.trigger_update",
    ),
]


router = routers.SimpleRouter()

router.register(
    rf"projects/(?P<project_slug>{DJANGO_SLUG_REGEX})/(?P<env_slug>{DJANGO_SLUG_REGEX})/variables",
    views.SharedEnvVariablesViewSet,
    basename="environment.variables",
)
urlpatterns += router.urls
