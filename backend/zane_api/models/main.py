# type: ignore
import time
import uuid
from typing import Optional

from django.conf import settings
from django.core.validators import MinLengthValidator, MinValueValidator
from django.db import models
from django.db.models import (
    Q,
    Case,
    Value,
    F,
    When,
    CheckConstraint,
    Subquery,
    OuterRef,
    Exists,
)
from django.utils.translation import gettext_lazy as _
from faker import Faker
from shortuuid.django_fields import ShortUUIDField
from django.utils import timezone
from ..utils import (
    strip_slash_if_exists,
    datetime_to_timestamp_string,
    generate_random_chars,
    replace_placeholders,
    format_duration,
)
from ..validators import validate_url_domain, validate_url_path, validate_env_name
from django.db.models import Manager
from .base import TimestampedModel
from git_connectors.models import GitHubApp, GitlabApp
from pathlib import PurePath
from git_connectors.dtos import GitCommitInfo
from typing import cast
from ..git_client import GitClient
import secrets
from ..constants import HEAD_COMMIT
from dataclasses import dataclass
from typing import Sequence, Self
from rest_framework.utils.serializer_helpers import ReturnDict
from ..dtos import ServiceSnapshot, DeploymentChangeDto
from git_connectors.constants import (
    PREVIEW_DEPLOYMENT_COMMENT_MARKDOWN_TEMPLATE,
    PREVIEW_DEPLOYMENT_BLOCKED_COMMENT_MARKDOWN_TEMPLATE,
    PREVIEW_DEPLOYMENT_DECLINED_COMMENT_MARKDOWN_TEMPLATE,
)
from datetime import timezone as tz
from typing import TYPE_CHECKING
from asgiref.sync import sync_to_async

if TYPE_CHECKING:
    from container_registry.models import SharedRegistryCredentials  # noqa: F401


class Project(TimestampedModel):
    environments: Manager["Environment"]
    preview_templates: Manager["PreviewEnvTemplate"]
    services: Manager["Service"]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    slug = models.SlugField(max_length=255, unique=True)
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix="prj_",
    )
    description = models.TextField(blank=True, null=True)

    @property
    async def abuild_registry(self):
        return await sync_to_async(lambda: self.build_registry)()

    @property
    def production_env(self):
        return self.environments.get(name=Environment.PRODUCTION_ENV_NAME)

    @property
    def default_preview_template(self):
        return (
            self.preview_templates.filter(is_default=True)
            .select_related("base_environment")
            .get()
        )

    @property
    async def adefault_preview_template(self):
        return await (
            self.preview_templates.filter(is_default=True)
            .select_related("base_environment")
            .aget()
        )

    @property
    async def aproduction_env(self):
        return await self.environments.aget(name=Environment.PRODUCTION_ENV_NAME)

    @property
    def create_task_id(self):
        return f"create-{self.id}-{datetime_to_timestamp_string(self.created_at)}"

    def __str__(self):
        return f"Project({self.slug})"

    class Meta:
        ordering = ["-updated_at"]


class URL(models.Model):
    ID_PREFIX = "url_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    domain = models.CharField(max_length=1000, validators=[validate_url_domain])
    base_path = models.CharField(default="/", validators=[validate_url_path])
    strip_prefix = models.BooleanField(default=True)
    redirect_to = models.JSONField(max_length=2000, null=True)
    associated_port = models.PositiveIntegerField(null=True)

    @classmethod
    def generate_default_domain(
        cls,
        service: "BaseService",
        root_domain: str = settings.ROOT_DOMAIN,
    ):
        return f"{service.project.slug}-{service.slug}-{generate_random_chars(10).lower()}.{root_domain.removeprefix('*.')}"

    def __repr__(self):
        base_path = (
            "/"
            if self.base_path == "/"
            else strip_slash_if_exists(
                self.base_path, strip_start=False, strip_end=True
            )
        )
        return f'URL(domain="{self.domain}"), base_path="{base_path}")'

    def __str__(self):
        base_path = (
            "/"
            if self.base_path == "/"
            else strip_slash_if_exists(
                self.base_path, strip_start=False, strip_end=True
            )
        )
        return f"{self.domain}{base_path}"

    class Meta:
        unique_together = (
            "domain",
            "base_path",
        )


class HealthCheck(models.Model):
    ID_PREFIX = "htc_"
    DEFAULT_TIMEOUT_SECONDS = 60
    DEFAULT_INTERVAL_SECONDS = 15
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class HealthCheckType(models.TextChoices):
        COMMAND = "COMMAND", _("Command")
        PATH = "PATH", _("Path")

    type = models.CharField(
        max_length=255,
        null=False,
        choices=HealthCheckType.choices,
        default=HealthCheckType.PATH,
    )
    value = models.CharField(max_length=255, null=False, default="/")
    interval_seconds = models.PositiveIntegerField(default=DEFAULT_INTERVAL_SECONDS)
    timeout_seconds = models.PositiveIntegerField(default=DEFAULT_TIMEOUT_SECONDS)
    associated_port = models.PositiveIntegerField(null=True)


class BaseService(TimestampedModel):
    # This limitation is because the length of a network alias on docker can only
    # go up to 86 chars, and by calculating with the additional prefixes and suffixes added the alias
    # the max size of the prefix+suffix is `48` characters
    # see: https://github.com/moby/moby/issues/37971 and https://github.com/moby/moby/issues/36402
    slug = models.SlugField(max_length=38)
    project = models.ForeignKey(
        to=Project, on_delete=models.CASCADE, related_name="services"
    )
    volumes = models.ManyToManyField(to="Volume")
    ports = models.ManyToManyField(to="PortConfiguration")
    urls = models.ManyToManyField(to=URL)
    healthcheck = models.ForeignKey(
        to=HealthCheck, null=True, on_delete=models.SET_NULL
    )
    network_alias = models.CharField(max_length=300, null=True)
    resource_limits = models.JSONField(
        max_length=255,
        null=True,
    )
    deploy_token = models.CharField(
        max_length=35,
        null=True,
        unique=True,
    )
    configs = models.ManyToManyField(to="Config")

    @classmethod
    def generate_network_alias(cls, instance: Self):
        return f"zn-{instance.slug}-{instance.unprefixed_id}"

    @property
    def host_volumes(self):
        return self.volumes.filter(host_path__isnull=False)

    @property
    def docker_volumes(self):
        return self.volumes.filter(host_path__isnull=True)

    class Meta:
        abstract = True

    def delete_resources(self):
        self.ports.filter().delete()
        self.urls.filter().delete()
        self.volumes.filter().delete()
        self.configs.filter().delete()
        if self.healthcheck is not None:
            self.healthcheck.delete()


class PortConfiguration(models.Model):
    ID_PREFIX = "prt_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    host = models.PositiveIntegerField(default=0)
    forwarded = models.PositiveIntegerField()

    def __str__(self):
        host_port = 80 if self.host is None else self.host
        return f"PortConfiguration({host_port} -> {self.forwarded})"

    class Meta:
        indexes = [models.Index(fields=["host"])]


class BaseEnvVariable(models.Model):
    key = models.CharField(max_length=255, validators=[validate_env_name])
    value = models.TextField(blank=True)

    class Meta:
        abstract = True


class EnvVariable(BaseEnvVariable):
    ID_PREFIX = "env_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    service: models.ForeignKey["Service"] = models.ForeignKey(
        to="Service",
        on_delete=models.CASCADE,
        related_name="env_variables",
    )

    def __str__(self):
        return f"DockerEnvVariable({self.key})"

    class Meta:
        unique_together = ["key", "service"]


class Service(BaseService):
    deployments: Manager["Deployment"]
    changes: Manager["DeploymentChange"]
    ports: Manager["PortConfiguration"]
    preview_environments: Manager["PreviewEnvMetadata"]
    env_variables: Manager[EnvVariable]
    urls: Manager[URL]
    volumes: Manager["Volume"]
    configs: Manager["Config"]
    project_id: str

    class ServiceType(models.TextChoices):
        DOCKER_REGISTRY = "DOCKER_REGISTRY", _("Docker repository")
        GIT_REPOSITORY = "GIT_REPOSITORY", _("Git repository")

    class Builder(models.TextChoices):
        DOCKERFILE = "DOCKERFILE", _("Dockerfile")
        STATIC_DIR = "STATIC_DIR", _("Static directory")
        NIXPACKS = "NIXPACKS", _("Nixpacks")
        RAILPACK = "RAILPACK", _("Railpack")

    ID_PREFIX = "srv_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    image = models.CharField(max_length=510, null=True)
    credentials = models.JSONField(
        max_length=255,
        null=True,
    )
    command = models.TextField(null=True, blank=True)

    environment: models.ForeignKey["Environment"] = models.ForeignKey(
        to="Environment",
        on_delete=models.CASCADE,
        related_name="services",
    )

    container_registry_credentials = models.ForeignKey["SharedRegistryCredentials"](
        to="container_registry.SharedRegistryCredentials",
        on_delete=models.PROTECT,
        related_name="services",
        null=True,
    )

    git_app = models.ForeignKey["GitApp"](
        to="GitApp", on_delete=models.PROTECT, related_name="services", null=True
    )

    type = models.CharField(
        max_length=15, choices=ServiceType.choices, default=ServiceType.DOCKER_REGISTRY
    )

    # git attributes
    repository_url = models.URLField(max_length=2048, null=True)
    branch_name = models.CharField(max_length=255, null=True)
    commit_sha = models.CharField(max_length=45, null=True)

    # Auto deploy options (only considered in git services)
    auto_deploy_enabled = models.BooleanField(default=True)
    watch_paths = models.CharField(
        max_length=2048, null=True, blank=False, default=None
    )
    cleanup_queue_on_auto_deploy = models.BooleanField(default=True)

    # Preview env options (only considered in git services)
    pr_preview_envs_enabled = models.BooleanField(default=True)

    builder = models.CharField(max_length=20, choices=Builder.choices, null=True)
    dockerfile_builder_options = models.JSONField(null=True)
    # JSON object with this content :
    # {
    #    "build_context_dir": "./",
    #    "dockerfile_path": "./Dockerfile",
    #    "build_target": "builder",
    # }

    static_dir_builder_options = models.JSONField(null=True)
    # JSON object with this content :
    # {
    #    "publish_directory": "./",
    #    "not_found_page": "404.html",
    #    "index_page": "index.html",
    #    "is_spa": False,
    #    "generated_caddyfile": """...""", <-- cannot pass this -> send to the user though
    # }

    nixpacks_builder_options = models.JSONField(null=True)
    # JSON object with this content :
    # {
    #    "build_directory": "./",
    #    "custom_install_command": None,
    #    "custom_build_command": None,
    #    "custom_start_command": None,
    #
    #    == FOR A STATIC OUTPUT ==
    #    "is_static": false,
    #    "publish_directory": "./",
    #    "is_spa": False,
    #    "not_found_page": "404.html",
    #    "index_page": "index.html",
    #    "generated_caddyfile": None, <-- cannot pass this -> send to the user though
    # }

    railpack_builder_options = models.JSONField(null=True)
    # JSON object with this content :
    # {
    #    "build_directory": "./",
    #    "custom_install_command": None,
    #    "custom_build_command": None,
    #    "custom_start_command": None,
    #
    #    == FOR A STATIC OUTPUT ==
    #    "is_static": false,
    #    "publish_directory": "./",
    #    "is_spa": False,
    #    "not_found_page": "404.html",
    #    "index_page": "index.html",
    #    "generated_caddyfile": None, <-- cannot pass this -> send to the user though
    # }

    def __str__(self):
        return (
            f"Service(slug={self.slug}, id={self.id}, environment={self.environment})"
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "project", "environment"],
                name="unique_slug_per_env_and_project",
            ),
            models.UniqueConstraint(
                fields=["network_alias", "project", "environment"],
                name="unique_network_alias_per_env_and_project",
            ),
        ]
        indexes = [models.Index(fields=["repository_url"])]

    def match_paths(self, paths: set[str]) -> bool:
        if not self.watch_paths:
            return True
        return any(PurePath(path).full_match(self.watch_paths) for path in paths)

    @classmethod
    def get_services_triggered_by_pull_request_event(
        self,
        gitapp: "GitApp",
        repository_url: str,
    ):
        # Subquery to check for mismatched git_app change on the service
        # Ex: the service has been updated from using a github app to a gitlab app
        # in this case, the gitlab app change will take precedence
        # This is done because we want
        mismatched_changes_subquery = Subquery(
            DeploymentChange.objects.filter(
                Q(
                    service=OuterRef("pk"),
                    field=DeploymentChange.ChangeField.GIT_SOURCE,
                    applied=False,
                    service__auto_deploy_enabled=True,
                    service__pr_preview_envs_enabled=True,
                )
                & ~Q(new_value__git_app__id=gitapp.id),
            )
        )
        # For services that haven't been deployed yet
        # or ones where the service has been updated with a new github app
        changes_subquery = (
            DeploymentChange.objects.filter(
                new_value__git_app__id=gitapp.id,
                new_value__repository_url=repository_url,
                field=DeploymentChange.ChangeField.GIT_SOURCE,
                applied=False,
                service__auto_deploy_enabled=True,
                service__pr_preview_envs_enabled=True,
            )
            .select_related("service")
            .values_list("service__id", flat=True)
        )

        # SubQuery to get the base environment of the default preview metadata of the service
        # we use this to only filter services that are included in the default
        # preview of the project (i.e. services whose environment matches the base_environment
        # defined in the default preview template).
        default_base_env_subquery = Subquery(
            PreviewEnvTemplate.objects.filter(
                project=OuterRef("project"),
                is_default=True,
            ).values("base_environment_id")[:1]
        )

        affected_services = (
            Service.objects.filter(
                Q(
                    repository_url=repository_url,
                    auto_deploy_enabled=True,
                    pr_preview_envs_enabled=True,
                    git_app=gitapp,
                    environment__is_preview=False,
                )
                | Q(id__in=changes_subquery)
            )
            .annotate(default_base_env_id=default_base_env_subquery)
            .filter(environment_id=F("default_base_env_id"))
            .annotate(has_mismatch=Exists(mismatched_changes_subquery))
            .filter(has_mismatch=False)
            .select_related(
                "project",
                "healthcheck",
                "environment",
                "git_app",
                "git_app__github",
                "git_app__gitlab",
            )
            .prefetch_related(
                "volumes",
                "ports",
                "urls",
                "env_variables",
                "changes",
                "configs",
            )
            .all()
        )
        return affected_services

    @classmethod
    def get_services_triggered_by_pull_request_sync_event(
        self,
        gitapp: "GitApp",
        pr_number: int,
        repository_url: str,
    ):
        affected_services = (
            Service.objects.filter(
                Q(
                    repository_url=repository_url,
                    git_app=gitapp,
                    environment__is_preview=True,
                    environment__preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST,
                    environment__preview_metadata__head_repository_url=repository_url,
                    environment__preview_metadata__git_app=gitapp,
                    environment__preview_metadata__pr_number=pr_number,
                    environment__preview_metadata__deploy_state=PreviewEnvMetadata.PreviewDeployState.APPROVED,
                )
            )
            .select_related(
                "project",
                "healthcheck",
                "environment",
                "git_app",
                "git_app__github",
                "git_app__gitlab",
            )
            .prefetch_related(
                "volumes",
                "ports",
                "urls",
                "env_variables",
                "changes",
                "configs",
            )
            .all()
        )
        return affected_services

    @classmethod
    def get_services_triggered_by_push_event(
        self,
        gitapp: "GitApp",
        branch_name: str,
        repository_url: str,
    ):
        # Subquery to check for mismatched git_app change on the service
        # Ex: the service has been updated from using a github app to a gitlab app
        # in this case, the gitlab app change will take precedence
        # This is done because we want
        mismatched_changes_subquery = Subquery(
            DeploymentChange.objects.filter(
                Q(
                    service=OuterRef("pk"),
                    field=DeploymentChange.ChangeField.GIT_SOURCE,
                    applied=False,
                    service__auto_deploy_enabled=True,
                )
                & ~Q(new_value__git_app__id=gitapp.id),
            )
        )

        # For services that haven't been deployed yet
        # or ones where the service has been updated with a new github app
        changes_subquery = (
            DeploymentChange.objects.filter(
                new_value__git_app__id=gitapp.id,
                new_value__branch_name=branch_name,
                new_value__commit_sha=HEAD_COMMIT,
                new_value__repository_url=repository_url,
                field=DeploymentChange.ChangeField.GIT_SOURCE,
                applied=False,
                service__auto_deploy_enabled=True,
            )
            .select_related("service")
            .values_list("service__id", flat=True)
        )

        affected_services = (
            Service.objects.filter(
                Q(
                    repository_url=repository_url,
                    auto_deploy_enabled=True,
                    git_app=gitapp,
                    branch_name=branch_name,
                    commit_sha=HEAD_COMMIT,
                )
                | Q(id__in=changes_subquery)
            )
            .annotate(has_mismatch=Exists(mismatched_changes_subquery))
            .filter(has_mismatch=False)
            .filter(
                # Ignore push made on pull requests & merge requests,
                # since there are already events on pull requests to signal new pushes
                ~Q(
                    environment__preview_metadata__source_trigger=Environment.PreviewSourceTrigger.PULL_REQUEST
                )
            )
            .select_related(
                "project",
                "healthcheck",
                "environment",
                "git_app",
                "git_app__github",
                "git_app__gitlab",
            )
            .prefetch_related(
                "volumes",
                "ports",
                "urls",
                "env_variables",
                "changes",
                "configs",
            )
            .all()
        )
        return affected_services

    def prepare_new_docker_deployment(
        self,
        trigger_method: Optional[str] = None,
        commit_message: Optional[str] = None,
        is_redeploy_of: Optional["Deployment"] = None,
    ):
        from ..serializers import ServiceSerializer

        new_deployment = Deployment(
            service=self,
            commit_message=commit_message if commit_message else "update service",
            trigger_method=(
                trigger_method
                if trigger_method is not None
                else Deployment.DeploymentTriggerMethod.MANUAL
            ),
            is_redeploy_of=is_redeploy_of,
        )

        new_deployment.save()

        self.apply_pending_changes(deployment=new_deployment)

        ports = (
            self.urls.filter(associated_port__isnull=False)
            .values_list("associated_port", flat=True)
            .distinct()
        )
        for port in ports:
            DeploymentURL.generate_for_deployment(
                deployment=new_deployment,
                service=self,
                port=port,
            )

        latest_deployment = self.latest_production_deployment

        new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
        new_deployment.service_snapshot = ServiceSerializer(self).data
        new_deployment.save()
        return new_deployment

    def prepare_new_git_deployment(
        self,
        ignore_build_cache=False,
        trigger_method: Optional[str] = None,
        commit: Optional[GitCommitInfo] = None,
        is_redeploy_of: Optional["Deployment"] = None,
    ):
        from ..serializers import ServiceSerializer

        new_deployment = Deployment(
            service=self,
            commit_message="-",
            ignore_build_cache=ignore_build_cache,
            trigger_method=(
                trigger_method
                if trigger_method is not None
                else Deployment.DeploymentTriggerMethod.MANUAL
            ),
            is_redeploy_of=is_redeploy_of,
        )

        if commit:
            new_deployment.commit_sha = commit.sha
            new_deployment.commit_message = commit.message
            new_deployment.commit_author_name = commit.author_name

        new_deployment.save()

        self.apply_pending_changes(deployment=new_deployment)

        ports = (
            self.urls.filter(associated_port__isnull=False)
            .values_list("associated_port", flat=True)
            .distinct()
        )
        for port in ports:
            DeploymentURL.generate_for_deployment(
                deployment=new_deployment,
                service=self,
                port=port,
            )

        latest_deployment = self.latest_production_deployment

        if commit is None:
            commit_sha = self.commit_sha
            if commit_sha == HEAD_COMMIT:
                git_client = GitClient()
                repo_url = cast(str, self.repository_url)
                if self.git_app is not None:
                    if self.git_app.github is not None:
                        repo_url = self.git_app.github.get_authenticated_repository_url(
                            repo_url
                        )
                    if self.git_app.gitlab is not None:
                        repo_url = self.git_app.gitlab.get_authenticated_repository_url(
                            repo_url
                        )
                commit_sha = (
                    git_client.resolve_commit_sha_for_branch(repo_url, self.branch_name)
                    or HEAD_COMMIT
                )
            new_deployment.commit_sha = commit_sha

        new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
        new_deployment.service_snapshot = ServiceSerializer(self).data
        new_deployment.save()
        return new_deployment

    @property
    def git_repository(self):
        if self.git_app is not None and self.repository_url is not None:
            if self.git_app.github is not None:
                return self.git_app.github.repositories.filter(
                    url=self.repository_url.rstrip("/")
                ).first()
            elif self.git_app.gitlab is not None:
                return self.git_app.gitlab.repositories.filter(
                    url=self.repository_url.rstrip("/")
                ).first()
        return None

    @property
    def next_git_repository(self):
        source_change = self.changes.filter(
            field=DeploymentChange.ChangeField.GIT_SOURCE,
            new_value__isnull=False,
            applied=False,
        ).first()
        if (
            source_change is not None
            and source_change.new_value.get("git_app") is not None
        ):
            repository_url: str = source_change.new_value["repository_url"]
            gitapp = (
                GitApp.objects.filter(id=source_change.new_value["git_app"]["id"])
                .select_related("github", "gitlab")
                .first()
            )

            if gitapp is not None:
                if gitapp.github is not None:
                    return gitapp.github.repositories.filter(
                        url=repository_url.rstrip("/")
                    ).first()
                if gitapp.gitlab is not None:
                    return gitapp.gitlab.repositories.filter(
                        url=repository_url.rstrip("/")
                    ).first()
        return None

    @property
    def unprefixed_id(self):
        return self.id.replace(self.ID_PREFIX, "") if self.id is not None else None

    @property
    def http_logs(self):
        return HttpLog.objects.filter(service_id=self.id)

    @property
    def metrics(self):
        return ServiceMetrics.objects.filter(service=self)

    @property
    def global_network_alias(self):
        return f"{self.network_alias}.{self.environment.id.replace(Environment.ID_PREFIX, '')}.{settings.ZANE_INTERNAL_DOMAIN}"

    @property
    def network_aliases(self):
        return (
            [
                f"{self.network_alias}.{settings.ZANE_INTERNAL_DOMAIN}",
                self.network_alias,
            ]
            if self.network_alias is not None
            else []
        )

    @property
    def system_env_variables(self) -> list[dict[str, str]]:
        domains = ",".join(
            [url.domain for url in self.urls.filter(associated_port__isnull=False)]
        )
        return [
            {
                "key": "ZANE",
                "value": "true",
                "comment": "Is the service deployed on zaneops?",
            },
            {
                "key": "ZANE_DOMAINS",
                "value": domains,
                "comment": "comma separated list of the all the domains where this service is accessible",
            },
            {
                "key": "ZANE_ENVIRONMENT",
                "value": f"{self.environment.name}",
                "comment": "The current environment where the service is deployed",
            },
            {
                "key": "ZANE_PRIVATE_DOMAIN",
                "value": f"{self.network_alias}.{settings.ZANE_INTERNAL_DOMAIN}",
                "comment": "The domain used to reach this service on the same project",
            },
            {
                "key": "ZANE_GLOBAL_PRIVATE_DOMAIN",
                "value": self.global_network_alias,
                "comment": "The domain used to reach this service globally on ZaneOps",
            },
            {
                "key": "ZANE_DEPLOYMENT_TYPE",
                "value": (
                    "docker"
                    if self.type == Service.ServiceType.DOCKER_REGISTRY
                    else "git"
                ),
                "comment": "The type of the service",
            },
            {
                "key": "ZANE_SERVICE_ID",
                "value": self.id,
                "comment": "The service ID",
            },
            {
                "key": "ZANE_SERVICE_NAME",
                "value": self.slug,
                "comment": "The name of this service",
            },
            {
                "key": "ZANE_PROJECT_ID",
                "value": self.project_id,
                "comment": "The id for the project this service belongs to",
            },
            {
                "key": "ZANE_DEPLOYMENT_SLOT",
                "value": "{{deployment.slot}}",
                "comment": "The slot for each deployment it can be `blue` or `green`, this is also sent as the header `x-zane-dpl-slot`",
            },
            {
                "key": "ZANE_DEPLOYMENT_HASH",
                "value": "{{deployment.hash}}",
                "comment": "The hash of each deployment, this is also sent as a header `x-zane-dpl-hash`",
            },
        ]

    @property
    def latest_production_deployment(self):
        return (
            self.deployments.filter(is_current_production=True)
            .select_related(
                "service",
                "service__project",
                "service__environment",
                "service__healthcheck",
                "service__git_app",
            )
            .prefetch_related(
                "service__volumes",
                "service__configs",
                "service__urls",
                "service__ports",
                "service__env_variables",
            )
            .order_by("-queued_at")
            .first()
        )

    @property
    async def alatest_production_deployment(self):
        return await (
            self.deployments.filter(is_current_production=True)
            .select_related(
                "service",
                "service__project",
                "service__healthcheck",
                "service__environment",
                "service__git_app",
            )
            .prefetch_related(
                "service__volumes",
                "service__urls",
                "service__ports",
                "service__env_variables",
            )
            .order_by("-queued_at")
            .afirst()
        )

    @property
    def unapplied_changes(self):
        return self.changes.filter(applied=False)

    @property
    def applied_changes(self):
        return self.changes.filter(applied=True)

    @property
    def last_queued_deployment(self):
        return (
            self.deployments.filter(
                is_current_production=False,
                status=Deployment.DeploymentStatus.QUEUED,
            )
            .select_related(
                "service",
                "service__project",
                "service__healthcheck",
                "service__environment",
                "service__git_app",
            )
            .prefetch_related(
                "service__volumes",
                "service__urls",
                "service__ports",
                "service__env_variables",
            )
            .order_by("-queued_at")
            .first()
        )

    def apply_pending_changes(self, deployment: "Deployment"):
        from container_registry.models import SharedRegistryCredentials

        for change in self.unapplied_changes:
            match (change.field, self.type):
                case DeploymentChange.ChangeField.COMMAND, __:
                    setattr(self, change.field, change.new_value)
                case (
                    DeploymentChange.ChangeField.SOURCE,
                    Service.ServiceType.DOCKER_REGISTRY,
                ):
                    self.image = change.new_value.get("image")

                    # In practice, only `container_registry_credentials` is allowed
                    # but we keep the old credentials for backwards compatibility
                    credentials = change.new_value.get("credentials")

                    self.credentials = (
                        None
                        if credentials is None
                        else {
                            "username": credentials.get("username"),
                            "password": credentials.get("password"),
                        }
                    )

                    registry_credentials = change.new_value.get(
                        "container_registry_credentials"
                    )
                    if registry_credentials is not None:
                        self.container_registry_credentials = (
                            SharedRegistryCredentials.objects.get(
                                id=registry_credentials["id"]
                            )
                        )
                    else:
                        self.container_registry_credentials = None

                case (
                    DeploymentChange.ChangeField.GIT_SOURCE,
                    Service.ServiceType.GIT_REPOSITORY,
                ):
                    self.repository_url = change.new_value.get("repository_url")
                    self.branch_name = change.new_value.get("branch_name")
                    self.commit_sha = change.new_value.get("commit_sha", HEAD_COMMIT)
                    git_app = change.new_value.get("git_app")
                    if git_app is not None:
                        self.git_app = (
                            GitApp.objects.filter(id=git_app["id"])
                            .select_related("github", "gitlab")
                            .get()
                        )
                    else:
                        self.git_app = None
                case (
                    DeploymentChange.ChangeField.BUILDER,
                    Service.ServiceType.GIT_REPOSITORY,
                ):
                    builder_options = change.new_value["options"]
                    self.builder = change.new_value.get("builder")
                    match change.new_value.get("builder"):
                        case Service.Builder.DOCKERFILE:
                            self.dockerfile_builder_options = {
                                "dockerfile_path": builder_options["dockerfile_path"],
                                "build_context_dir": builder_options[
                                    "build_context_dir"
                                ],
                                "build_stage_target": builder_options[
                                    "build_stage_target"
                                ],
                            }
                        case Service.Builder.STATIC_DIR:
                            self.static_dir_builder_options = {
                                "publish_directory": builder_options[
                                    "publish_directory"
                                ],
                                "index_page": builder_options.get("index_page"),
                                "not_found_page": builder_options.get("not_found_page"),
                                "is_spa": builder_options.get("is_spa", False),
                                "generated_caddyfile": builder_options.get(
                                    "generated_caddyfile"
                                ),
                            }
                        case Service.Builder.NIXPACKS:
                            self.nixpacks_builder_options = {
                                "build_directory": builder_options["build_directory"],
                                "custom_install_command": builder_options.get(
                                    "custom_install_command"
                                ),
                                "custom_build_command": builder_options.get(
                                    "custom_build_command"
                                ),
                                "custom_start_command": builder_options.get(
                                    "custom_start_command"
                                ),
                                "is_static": builder_options["is_static"],
                                "publish_directory": builder_options[
                                    "publish_directory"
                                ],
                                "index_page": builder_options.get("index_page"),
                                "not_found_page": builder_options.get("not_found_page"),
                                "is_spa": builder_options.get("is_spa", False),
                                "generated_caddyfile": builder_options.get(
                                    "generated_caddyfile"
                                ),
                            }
                        case Service.Builder.RAILPACK:
                            self.railpack_builder_options = {
                                "build_directory": builder_options["build_directory"],
                                "custom_install_command": builder_options.get(
                                    "custom_install_command"
                                ),
                                "custom_build_command": builder_options.get(
                                    "custom_build_command"
                                ),
                                "custom_start_command": builder_options.get(
                                    "custom_start_command"
                                ),
                                "is_static": builder_options["is_static"],
                                "publish_directory": builder_options[
                                    "publish_directory"
                                ],
                                "index_page": builder_options.get("index_page"),
                                "not_found_page": builder_options.get("not_found_page"),
                                "is_spa": builder_options.get("is_spa", False),
                                "generated_caddyfile": builder_options.get(
                                    "generated_caddyfile"
                                ),
                            }
                        case _:
                            raise NotImplementedError(
                                f"This builder `{change.new_value.get('builder')}` type has not yet been implemented"
                            )
                case DeploymentChange.ChangeField.RESOURCE_LIMITS, __:
                    if change.new_value is None:
                        self.resource_limits = None
                        continue
                    self.resource_limits = {
                        "cpus": change.new_value.get("cpus"),
                        "memory": change.new_value.get("memory"),
                    }
                case DeploymentChange.ChangeField.HEALTHCHECK, __:
                    if change.new_value is None:
                        if self.healthcheck is not None:
                            self.healthcheck.delete()
                            self.healthcheck = None
                        continue

                    if self.healthcheck is None:
                        self.healthcheck = HealthCheck()

                    self.healthcheck.type = change.new_value.get("type")
                    self.healthcheck.value = change.new_value.get("value")
                    self.healthcheck.associated_port = change.new_value.get(
                        "associated_port"
                    )
                    self.healthcheck.timeout_seconds = (
                        change.new_value.get("timeout_seconds")
                        or HealthCheck.DEFAULT_TIMEOUT_SECONDS
                    )
                    self.healthcheck.interval_seconds = (
                        change.new_value.get("interval_seconds")
                        or HealthCheck.DEFAULT_INTERVAL_SECONDS
                    )
                    self.healthcheck.save()
                case DeploymentChange.ChangeField.VOLUMES, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        fake = Faker()
                        Faker.seed(time.monotonic())
                        self.volumes.add(
                            Volume.objects.create(
                                container_path=change.new_value.get("container_path"),
                                host_path=change.new_value.get("host_path"),
                                mode=change.new_value.get("mode"),
                                name=change.new_value.get("name", fake.slug().lower()),
                            )
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.volumes.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        volume = self.volumes.get(id=change.item_id)
                        volume.host_path = change.new_value.get("host_path")
                        volume.container_path = change.new_value.get("container_path")
                        volume.mode = change.new_value.get("mode")
                        volume.name = change.new_value.get("name", volume.name)
                        volume.save()
                case DeploymentChange.ChangeField.CONFIGS, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        fake = Faker()
                        Faker.seed(time.monotonic())
                        self.configs.add(
                            Config.objects.create(
                                mount_path=change.new_value.get("mount_path"),
                                contents=change.new_value.get("contents"),
                                name=change.new_value.get("name", fake.slug().lower()),
                                language=change.new_value.get("language", "plaintext"),
                            )
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.configs.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        config = self.configs.get(id=change.item_id)
                        config.mount_path = change.new_value.get(
                            "mount_path", config.mount_path
                        )
                        new_contents = change.new_value.get("contents", config.contents)

                        if config.contents != new_contents:
                            config.version += 1

                        config.contents = new_contents
                        config.name = change.new_value.get("name", config.name)
                        config.language = change.new_value.get(
                            "language", config.language
                        )
                        config.save()
                case DeploymentChange.ChangeField.ENV_VARIABLES, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        EnvVariable.objects.create(
                            key=change.new_value.get("key"),
                            value=change.new_value.get("value"),
                            service=self,
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.env_variables.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        env = self.env_variables.get(id=change.item_id)
                        env.key = change.new_value.get("key")
                        env.value = change.new_value.get("value")
                        env.save()
                case DeploymentChange.ChangeField.URLS, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        self.urls.add(
                            URL.objects.create(
                                domain=change.new_value.get("domain"),
                                base_path=change.new_value.get("base_path"),
                                strip_prefix=change.new_value.get("strip_prefix"),
                                redirect_to=change.new_value.get("redirect_to"),
                                associated_port=change.new_value.get("associated_port"),
                            )
                        )
                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.urls.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        url = self.urls.get(id=change.item_id)
                        url.domain = change.new_value.get("domain")
                        url.base_path = change.new_value.get("base_path")
                        url.strip_prefix = change.new_value.get("strip_prefix")
                        url.redirect_to = change.new_value.get("redirect_to")
                        url.associated_port = change.new_value.get("associated_port")
                        url.save()
                case DeploymentChange.ChangeField.PORTS, __:
                    if change.type == DeploymentChange.ChangeType.ADD:
                        self.ports.add(
                            PortConfiguration.objects.create(
                                host=change.new_value.get("host"),
                                forwarded=change.new_value.get("forwarded"),
                            )
                        )

                    if change.type == DeploymentChange.ChangeType.DELETE:
                        self.ports.get(id=change.item_id).delete()
                    if change.type == DeploymentChange.ChangeType.UPDATE:
                        port = self.ports.get(id=change.item_id)
                        port.host = change.new_value.get("host")
                        port.forwarded = change.new_value.get("forwarded")
                        port.save()

        self.unapplied_changes.update(applied=True, deployment=deployment)
        self.save()
        self.refresh_from_db()

    def clone(self, environment: "Environment"):
        service = Service.objects.create(
            slug=self.slug,
            environment=environment,
            project=self.project,
            network_alias=self.network_alias,
            type=self.type,
            deploy_token=secrets.token_hex(16),
            auto_deploy_enabled=self.auto_deploy_enabled,
            watch_paths=self.watch_paths,
            cleanup_queue_on_auto_deploy=self.cleanup_queue_on_auto_deploy,
            pr_preview_envs_enabled=self.pr_preview_envs_enabled,
        )
        return service

    def add_change(self, change: "DeploymentChange"):
        change.service = self
        match change.field:
            case (
                DeploymentChange.ChangeField.BUILDER
                | DeploymentChange.ChangeField.GIT_SOURCE
                | DeploymentChange.ChangeField.SOURCE
                | DeploymentChange.ChangeField.COMMAND
                | DeploymentChange.ChangeField.HEALTHCHECK
                | DeploymentChange.ChangeField.RESOURCE_LIMITS
            ):
                change_for_field = self.unapplied_changes.filter(
                    field=change.field
                ).first()
                if change_for_field is not None:
                    change_for_field.new_value = change.new_value
                else:
                    change_for_field = change
                change_for_field.save()
            case _:
                change.save()


class ServiceMetrics(TimestampedModel):
    cpu_percent = models.FloatField()
    memory_bytes = models.PositiveBigIntegerField()
    net_tx_bytes = models.PositiveBigIntegerField()
    net_rx_bytes = models.PositiveBigIntegerField()
    disk_read_bytes = models.PositiveBigIntegerField()
    disk_writes_bytes = models.PositiveBigIntegerField()

    service = models.ForeignKey(to=Service, on_delete=models.CASCADE)
    deployment = models.ForeignKey["Deployment"](
        to="Deployment", on_delete=models.CASCADE
    )

    class Meta:
        indexes = [models.Index(fields=["created_at"])]


class Volume(TimestampedModel):
    ID_PREFIX = "vol_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)

    class VolumeMode(models.TextChoices):
        READ_ONLY = "READ_ONLY", _("Read-Only")
        READ_WRITE = "READ_WRITE", _("Read-Write")

    mode = models.CharField(
        max_length=255,
        null=False,
        choices=VolumeMode.choices,
        default=VolumeMode.READ_WRITE,
    )
    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        validators=[MinLengthValidator(limit_value=1)],
    )
    container_path = models.CharField(max_length=255)
    host_path = models.CharField(
        max_length=255, null=True, validators=[validate_url_path]
    )

    def __str__(self):
        return f"Volume({self.name})"

    class Meta:
        indexes = [
            models.Index(fields=["host_path"]),
            models.Index(fields=["container_path"]),
        ]


class Config(TimestampedModel):
    ID_PREFIX = "cf_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)

    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        validators=[MinLengthValidator(limit_value=1)],
    )
    mount_path = models.CharField(max_length=255)
    contents = models.TextField(blank=True)
    language = models.CharField(default="plaintext", max_length=255)
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Config({self.name})"

    class Meta:
        indexes = [
            models.Index(fields=["mount_path"]),
            models.Index(fields=["version"]),
        ]


class DeploymentURL(models.Model):
    domain = models.URLField()
    port = models.PositiveIntegerField(default=80)
    deployment: models.ForeignKey["Deployment"] = models.ForeignKey(
        to="Deployment",
        on_delete=models.CASCADE,
        related_name="urls",
    )

    @classmethod
    def generate_for_deployment(
        cls,
        deployment: "Deployment",
        port: int,
        service: "Service",
    ):
        return cls.objects.create(
            domain=f"{service.project.slug}-{service.slug}-{deployment.hash.replace('_', '-')}-{generate_random_chars(10)}.{settings.ROOT_DOMAIN}".lower(),
            port=port,
            deployment=deployment,
        )

    class Meta:
        indexes = [models.Index(fields=["domain"])]


class BaseDeployment(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        abstract = True


class Deployment(BaseDeployment):
    service_id: str
    urls: Manager["DeploymentURL"]
    changes: Manager["DeploymentChange"]

    HASH_PREFIX = "dpl_dkr_"
    hash = ShortUUIDField(length=11, max_length=255, unique=True, prefix=HASH_PREFIX)
    is_redeploy_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True)

    class DeploymentTriggerMethod(models.TextChoices):
        MANUAL = "MANUAL", _("Manual")
        AUTO = "AUTO", _("Automatic")
        API = "API", _("API")

    class DeploymentStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        CANCELLED = "CANCELLED", _("Cancelled")
        CANCELLING = "CANCELLING", _("Cancelling")
        FAILED = "FAILED", _("Failed")
        PREPARING = "PREPARING", _("Preparing")
        BUILDING = "BUILDING", _("Building")
        STARTING = "STARTING", _("Starting")
        RESTARTING = "RESTARTING", _("Restarting")
        HEALTHY = "HEALTHY", _("Healthy")
        UNHEALTHY = "UNHEALTHY", _("Unhealthy")
        REMOVED = "REMOVED", _("Removed")
        SLEEPING = "SLEEPING", _("Sleeping")

    class DeploymentSlot(models.TextChoices):
        BLUE = "BLUE", _("Blue")
        GREEN = "GREEN", _("Green")

    slot = models.CharField(
        max_length=10,
        choices=DeploymentSlot.choices,
        default=DeploymentSlot.BLUE,
    )

    status = models.CharField(
        max_length=10,
        choices=DeploymentStatus.choices,
        default=DeploymentStatus.QUEUED,
    )
    status_reason = models.TextField(null=True, blank=True)
    is_current_production = models.BooleanField(default=False)
    service = models.ForeignKey(
        to=Service, on_delete=models.CASCADE, related_name="deployments"
    )
    service_snapshot = models.JSONField(null=True)
    commit_message = models.TextField(default="update service")

    trigger_method = models.CharField(
        max_length=15,
        choices=DeploymentTriggerMethod.choices,
        default=DeploymentTriggerMethod.MANUAL,
    )
    commit_sha = models.CharField(max_length=45, null=True)
    commit_author_name = models.TextField(max_length=1024, null=True)
    pull_request_number = models.PositiveIntegerField(null=True)
    ignore_build_cache = models.BooleanField(default=False)
    build_started_at = models.DateTimeField(null=True)
    build_finished_at = models.DateTimeField(null=True)

    @classmethod
    def get_next_deployment_slot(
        cls,
        latest_production_deployment: Optional["Deployment"],
    ) -> str:
        if (
            latest_production_deployment is not None
            and latest_production_deployment.slot == Deployment.DeploymentSlot.BLUE
            and latest_production_deployment.status
            != Deployment.DeploymentStatus.FAILED
            # 👆🏽 technically this can only be true for the initial deployment
            # for the next deployments, when they fail, they will not be promoted to production
        ):
            return Deployment.DeploymentSlot.GREEN
        return Deployment.DeploymentSlot.BLUE

    @classmethod
    def flag_deployments_for_cancellation(
        cls, service: Service, include_running_deployments=False
    ):
        cancellable_statuses = [Deployment.DeploymentStatus.QUEUED]
        active_statuses = [
            Deployment.DeploymentStatus.PREPARING,
            Deployment.DeploymentStatus.BUILDING,
            Deployment.DeploymentStatus.STARTING,
            Deployment.DeploymentStatus.RESTARTING,
        ]
        ignore_hash: Optional[str] = None
        if include_running_deployments:
            cancellable_statuses += active_statuses
        else:
            possibly_running_deployment = (
                cls.objects.filter(
                    Q(service=service)
                    & Q(status__in=cancellable_statuses + active_statuses)
                )
                .order_by("queued_at")
                .first()
            )
            if possibly_running_deployment is not None:
                ignore_hash = possibly_running_deployment.hash

        deployments_to_flag = cls.objects.filter(
            Q(service=service)
            & Q(status__in=cancellable_statuses)
            & ~Q(hash=ignore_hash)
        ).select_related("service")

        deployments_to_cancel: list[Deployment] = []
        for dpl in deployments_to_flag:
            deployments_to_cancel.append(dpl)

        deployments_to_flag.update(
            status=Case(
                When(
                    started_at__isnull=True,
                    then=Value(
                        Deployment.DeploymentStatus.CANCELLED,
                    ),
                ),
                default=F("status"),
                output_field=models.CharField(),
            ),
            status_reason=Case(
                When(
                    started_at__isnull=True,
                    then=Value(
                        "Cancelled due to new superseding deployment.",
                    ),
                ),
                default=F("status_reason"),
                output_field=models.CharField(),
            ),
        )
        return deployments_to_cancel

    @property
    def workflow_id(self):
        return f"deploy-{self.service.id}-{self.service.project_id}"

    @property
    def image_tag(self):
        # The repository name can only have max to 256 chars (including `/`)
        # the max slug length is 38 chars
        # the 108 + 108 + 2 (slashes) = 256
        return f"{self.service.project.slug[:108]}/{self.service.environment.name[:108]}/{self.service.slug}:{self.commit_sha}".lower()

    @property
    async def aimage_tag(self):
        return await sync_to_async(lambda: self.image_tag)()

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.service.project_id}"

    @property
    def metrics_schedule_id(self):
        return f"metrics-{self.hash}-{self.service_id}-{self.service.project_id}"

    @property
    def unprefixed_hash(self) -> str:
        return None if self.hash is None else self.hash.replace(self.HASH_PREFIX, "")

    @property
    def network_aliases(self):
        aliases = []
        if self.service is not None and len(self.service.network_aliases) > 0:
            aliases = self.service.network_aliases + [self.network_alias]
        return aliases

    @property
    def network_alias(self):
        return f"srv-{self.service.unprefixed_id}.{self.slot}.{settings.ZANE_INTERNAL_DOMAIN}".lower()

    class Meta:
        ordering = ("-queued_at",)
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_current_production"]),
        ]

    @property
    def http_logs(self):
        return HttpLog.objects.filter(deployment_id=self.hash)

    def __str__(self):
        return f"DockerDeployment(hash={self.hash}, service={self.service.slug}, project={self.service.project.slug}, status={self.status})"

    def get_pull_request_deployment_comment_body(self):
        service = self.service
        project = self.service.project
        environment = self.service.environment

        formated_datetime = self.updated_at.astimezone(tz.utc).strftime(
            "%b %-d, %Y %-I:%M%p"
        )

        preview_url = "`n/a`"

        first_service_url = service.urls.filter(
            associated_port__isnull=False, redirect_to__isnull=True
        ).first()

        if first_service_url is not None:
            preview_url = f"[Preview URL](//{first_service_url.domain}{first_service_url.base_path})"

        status_emoji_map = {
            "HEALTHY": "🟢",
            "FAILED": "❌",
            "QUEUED": "⏳",
            "PREPARING": "⏳",
            "BUILDING": "🔨",
            "STARTING": "▶️",
            "RESTARTING": "🔄",
            "CANCELLING": "⏹️",
            "CANCELLED": "🚫",
        }

        return replace_placeholders(
            PREVIEW_DEPLOYMENT_COMMENT_MARKDOWN_TEMPLATE,
            replacements=dict(
                dpl=dict(
                    service_fqdn=f"{project.slug}/{service.slug}",
                    service_url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/services/{service.slug}",
                    status=(
                        "Ready"
                        if self.status == Deployment.DeploymentStatus.HEALTHY
                        else self.status.capitalize()
                    ),
                    url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/services/{service.slug}/deployments/{self.hash}/build-logs",
                    updated_at=formated_datetime,
                    preview_url=preview_url,
                    status_icon=status_emoji_map[self.status],
                    duration="`n/a`",
                )
            ),
        )

    async def aget_pull_request_deployment_comment_body(self):
        service = self.service
        project = self.service.project
        environment = self.service.environment

        formated_datetime = self.updated_at.astimezone(tz.utc).strftime(
            "%b %-d, %Y %-I:%M%p"
        )

        preview_url = "`n/a`"

        first_service_url = await service.urls.filter(
            associated_port__isnull=False, redirect_to__isnull=True
        ).afirst()

        if first_service_url is not None:
            preview_url = f"[Visit Preview ↗](//{first_service_url.domain}{first_service_url.base_path})"

        status_emoji_map = {
            "HEALTHY": "🟢",
            "FAILED": "❌",
            "QUEUED": "⏳",
            "PREPARING": "⏳",
            "BUILDING": "🔨",
            "STARTING": "▶️",
            "RESTARTING": "🔄",
            "CANCELLING": "⏹️",
            "CANCELLED": "🚫",
        }

        deployment_duration = "`n/a`"

        if self.finished_at is not None and self.started_at is not None:
            duration = (self.finished_at - self.started_at).total_seconds()
            deployment_duration = format_duration(duration)

        return replace_placeholders(
            PREVIEW_DEPLOYMENT_COMMENT_MARKDOWN_TEMPLATE,
            replacements=dict(
                dpl=dict(
                    service_fqdn=f"{project.slug}/{service.slug}",
                    service_url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/services/{service.slug}",
                    status=(
                        "Ready"
                        if self.status == Deployment.DeploymentStatus.HEALTHY
                        else self.status.capitalize()
                    ),
                    url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/services/{service.slug}/deployments/{self.hash}/build-logs",
                    updated_at=formated_datetime,
                    preview_url=preview_url,
                    status_icon=status_emoji_map[self.status],
                    duration=deployment_duration,
                )
            ),
        )


class BaseDeploymentChange(TimestampedModel):
    class ChangeType(models.TextChoices):
        UPDATE = "UPDATE", _("update")
        DELETE = "DELETE", _("delete")
        ADD = "ADD", _("add")

    type = models.CharField(
        max_length=10,
        choices=ChangeType.choices,
    )
    field = models.CharField(max_length=255)
    item_id = models.CharField(max_length=255, null=True)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    applied = models.BooleanField(default=False)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["field"]),
            models.Index(fields=["type"]),
            models.Index(fields=["applied"]),
        ]


class DeploymentChange(BaseDeploymentChange):
    ID_PREFIX = "chg_dkr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class ChangeField(models.TextChoices):
        SOURCE = "source", _("source")
        GIT_SOURCE = "git_source", _("git_source")
        BUILDER = "builder", _("builder")
        COMMAND = "command", _("command")
        HEALTHCHECK = "healthcheck", _("healthcheck")
        VOLUMES = "volumes", _("volumes")
        ENV_VARIABLES = "env_variables", _("env variables")
        URLS = "urls", _("urls")
        PORTS = "ports", _("ports")
        RESOURCE_LIMITS = "resource_limits", _("resource limits")
        CONFIGS = "configs", _("configs")

    field = models.CharField(max_length=255, choices=ChangeField.choices)
    service = models.ForeignKey(
        to=Service, on_delete=models.CASCADE, related_name="changes"
    )
    deployment = models.ForeignKey(
        to=Deployment, on_delete=models.CASCADE, related_name="changes", null=True
    )

    def __str__(self):
        return (
            f"DockerDeploymentChange("
            f"\n\ttype={self.type},"
            f"\n\tfield={repr(self.field)},"
            f"\n\titem_id={repr(self.item_id)},"
            f"\n\told_value={repr(self.old_value)},"
            f"\n\tnew_value={repr(self.new_value)},"
            f"\n\tapplied={repr(self.applied)}"
            f"\n)"
        )


class Log(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    service_id = models.CharField(null=True)
    deployment_id = models.CharField(null=True)
    time = models.DateTimeField()

    class Meta:
        abstract = True


class HttpLog(Log):
    class RequestMethod(models.TextChoices):
        GET = "GET", _("GET")
        POST = "POST", _("POST")
        PUT = "PUT", _("PUT")
        DELETE = "DELETE", _("DELETE")
        PATCH = "PATCH", _("PATCH")
        OPTIONS = "OPTIONS", _("OPTIONS")
        HEAD = "HEAD", _("HEAD")

    class RequestProtocols(models.TextChoices):
        HTTP_1_0 = "HTTP/1.0", _("HTTP/1.0")
        HTTP_1_1 = "HTTP/1.1", _("HTTP/1.1")
        HTTP_2 = "HTTP/2.0", _("HTTP/2.0")
        HTTP_3 = "HTTP/3.0", _("HTTP/3.0")

    request_method = models.CharField(
        max_length=7,
        choices=RequestMethod.choices,
    )
    status = models.PositiveIntegerField()
    request_duration_ns = models.BigIntegerField()
    request_headers = models.JSONField()
    response_headers = models.JSONField()
    request_protocol = models.CharField(
        max_length=10,
        choices=RequestProtocols.choices,
        default=RequestProtocols.HTTP_1_1,
    )
    request_host = models.URLField(max_length=1000)
    request_path = models.CharField(max_length=2000)
    request_query = models.CharField(max_length=2000, null=True, blank=True)
    request_ip = models.GenericIPAddressField()
    request_id = models.CharField(null=True, max_length=255)
    request_user_agent = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["deployment_id"]),
            models.Index(fields=["service_id"]),
            models.Index(fields=["request_method"]),
            models.Index(fields=["status"]),
            models.Index(fields=["request_host"]),
            models.Index(fields=["request_path"]),
            models.Index(fields=["time"]),
            models.Index(fields=["request_user_agent"]),
            models.Index(fields=["request_ip"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["request_query"]),
        ]
        ordering = ("-time",)


class PreviewEnvMetadata(models.Model):
    environment: "Environment"

    class PreviewSourceTrigger(models.TextChoices):
        API = "API", _("Api")
        PULL_REQUEST = "PULL_REQUEST", _("Pull request")

    class PreviewDeployState(models.TextChoices):
        APPROVED = "APPROVED", _("Approved")
        PENDING = "PENDING", _("Pending")

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="preview_environments",
    )

    template: models.ForeignKey["PreviewEnvTemplate"] = models.ForeignKey(
        to="PreviewEnvTemplate",
        on_delete=models.PROTECT,
        related_name="preview_metas",
    )
    branch_name = models.CharField(max_length=255)
    commit_sha = models.CharField(max_length=255, default=HEAD_COMMIT)
    pr_number = models.PositiveIntegerField(
        null=True, validators=[MinValueValidator(1)]
    )
    pr_comment_id = models.PositiveBigIntegerField(
        null=True, validators=[MinValueValidator(1)]
    )
    pr_title = models.CharField(max_length=1000, null=True, blank=True)
    pr_author = models.CharField(max_length=1000, null=True, blank=True)
    pr_base_repo_url = models.URLField(null=True, blank=True)
    pr_base_branch_name = models.URLField(null=True, blank=True)
    external_url = models.URLField()
    head_repository_url = models.URLField()
    git_app: models.ForeignKey["GitApp"] = models.ForeignKey(
        "GitApp",
        on_delete=models.PROTECT,
    )

    deploy_state = models.CharField(
        choices=PreviewDeployState.choices,
        default="PENDING",
        max_length=30,
    )
    source_trigger = models.CharField(
        max_length=30,
        choices=PreviewSourceTrigger.choices,
    )
    ttl_seconds = models.PositiveIntegerField(null=True)
    auto_teardown = models.BooleanField(default=True)
    auth_enabled = models.BooleanField(default=False)
    auth_user = models.CharField(null=True)
    auth_password = models.CharField(null=True)

    def get_pull_request_deployment_blocked_comment_body(self, service: Service):
        project = service.project
        environment = service.environment

        return replace_placeholders(
            PREVIEW_DEPLOYMENT_BLOCKED_COMMENT_MARKDOWN_TEMPLATE,
            replacements=dict(
                dpl=dict(
                    service_fqdn=f"{project.slug}/{service.slug}",
                    service_url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/services/{service.slug}",
                    pr_author=self.pr_author,
                    approval_url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/review-deployment",
                )
            ),
        )

    def get_pull_request_deployment_declined_comment_body(self, service: Service):
        project = service.project
        environment = service.environment

        return replace_placeholders(
            PREVIEW_DEPLOYMENT_DECLINED_COMMENT_MARKDOWN_TEMPLATE,
            replacements=dict(
                dpl=dict(
                    service_fqdn=f"{project.slug}/{service.slug}",
                    service_url=f"//{settings.ZANE_APP_DOMAIN}/project/{project.slug}/{environment.name}/services/{service.slug}",
                )
            ),
        )


@dataclass
class CloneEnvPreviewPayload:
    template: "PreviewEnvTemplate"
    metadata: PreviewEnvMetadata


class Environment(TimestampedModel):
    services: Manager[Service]
    variables: Manager["SharedEnvVariable"]
    PRODUCTION_ENV_NAME = "production"

    class PreviewSourceTrigger(models.TextChoices):
        API = "API", _("Api")
        PULL_REQUEST = "PULL_REQUEST", _("Pull request")

    ID_PREFIX = "project_env_"
    id = ShortUUIDField(
        length=15, max_length=255, unique=True, prefix=ID_PREFIX, primary_key=True
    )

    name = models.SlugField(max_length=255)
    project = models.ForeignKey(
        to=Project, on_delete=models.CASCADE, related_name="environments"
    )
    is_preview = models.BooleanField(default=False)

    # If it's a preview, this field is not null
    preview_metadata = models.OneToOneField(
        to=PreviewEnvMetadata,
        null=True,
        on_delete=models.SET_NULL,
        related_name="environment",
    )

    def __str__(self):
        return f"Environment(project={self.project.slug}, name={self.name}, is_preview={self.is_preview})"

    @property
    def workflow_id(self) -> str:
        return f"create-env-{self.project_id}-{self.id}"

    @property
    def archive_workflow_id(self) -> str:
        return f"archive-env-{self.project_id}-{self.id}"

    @property
    def delayed_archive_workflow_id(self) -> str:
        return f"delayed-archive-env-{self.project_id}-{self.id}"

    @property
    def is_production(self):
        return self.name == self.PRODUCTION_ENV_NAME  # production is a reserved name

    def clone(
        self, env_name: str, preview_data: Optional[CloneEnvPreviewPayload] = None
    ):
        from ..serializers import ServiceSerializer
        from ..views.helpers import apply_changes_to_snapshot, diff_service_snapshots

        if preview_data is not None:
            assert preview_data.template.base_environment.id == self.id

        new_environment = self.project.environments.create(
            name=env_name,
            is_preview=preview_data is not None,
            preview_metadata=(
                preview_data.metadata if preview_data is not None else None
            ),
        )

        # Step 1: copy variables
        cloned_variables: dict[str, str] = {
            variable.key: variable.value for variable in self.variables.all()
        }

        if preview_data is not None:
            for variable in preview_data.template.variables.all():
                cloned_variables[variable.key] = variable.value

        if len(cloned_variables) > 0:
            new_environment.variables.bulk_create(
                [
                    SharedEnvVariable(key=key, value=value, environment=new_environment)
                    for key, value in cloned_variables.items()
                ]
            )
        services_to_clone: Sequence[Service] = []

        # Step 2: clone services
        if preview_data is None:
            services_to_clone = (
                self.services.select_related(
                    "healthcheck",
                    "project",
                    "environment",
                )
                .prefetch_related(
                    "volumes",
                    "ports",
                    "urls",
                    "env_variables",
                    "changes",
                    "configs",
                )
                .all()
            )
        else:
            match preview_data.template.clone_strategy:
                case PreviewEnvTemplate.PreviewCloneStrategy.ALL:
                    services_to_clone = [
                        *self.services.select_related(
                            "healthcheck",
                            "project",
                            "environment",
                        )
                        .prefetch_related(
                            "volumes",
                            "ports",
                            "urls",
                            "env_variables",
                            "changes",
                            "configs",
                        )
                        .all()
                    ]

                case PreviewEnvTemplate.PreviewCloneStrategy.ONLY:
                    services_to_clone = [
                        *self.services.filter(
                            id__in=preview_data.template.services_to_clone.values_list(
                                "id", flat=True
                            )
                        )
                        .select_related(
                            "healthcheck",
                            "project",
                            "environment",
                        )
                        .prefetch_related(
                            "volumes",
                            "ports",
                            "urls",
                            "env_variables",
                            "changes",
                            "configs",
                        )
                        .all()
                    ]

            if preview_data.metadata.service.id not in [
                service.id for service in services_to_clone
            ]:
                services_to_clone.append(preview_data.metadata.service)

        for service in services_to_clone:
            cloned_service = service.clone(environment=new_environment)
            current = cast(ReturnDict, ServiceSerializer(cloned_service).data)

            target_without_changes = cast(ReturnDict, ServiceSerializer(service).data)
            target = apply_changes_to_snapshot(
                ServiceSnapshot.from_dict(target_without_changes),
                [
                    DeploymentChangeDto.from_dict(
                        dict(
                            type=ch.type,
                            field=ch.field,
                            new_value=ch.new_value,
                            old_value=ch.old_value,
                            item_id=ch.item_id,
                        )
                    )
                    for ch in service.unapplied_changes.all()
                ],
            )

            changes = diff_service_snapshots(current, target)

            for change in changes:
                match change.field:
                    case DeploymentChange.ChangeField.URLS:
                        if change.new_value.get("redirect_to") is not None:  # type: ignore
                            # we don't copy over redirected urls, as they might not be needed
                            continue

                        root_domain = settings.ROOT_DOMAIN
                        if preview_data is not None:
                            root_domain = (
                                preview_data.template.preview_root_domain
                                or settings.ROOT_DOMAIN
                            )
                        # We also don't want to copy the same URL because it might clash with the original service
                        change.new_value["domain"] = URL.generate_default_domain(
                            cloned_service, root_domain
                        )  # type: ignore
                    case DeploymentChange.ChangeField.PORTS:
                        # Don't copy port changes to not cause conflicts with other ports
                        continue
                    case DeploymentChange.ChangeField.GIT_SOURCE if (
                        preview_data is not None
                        and service == preview_data.metadata.service
                    ):
                        # overwrite the `branch_name` and `commit_sha`
                        source_data = cast(dict, change.new_value)
                        source_data["repository_url"] = (
                            preview_data.metadata.head_repository_url
                        )
                        source_data["branch_name"] = preview_data.metadata.branch_name
                        source_data["commit_sha"] = preview_data.metadata.commit_sha
                change.service = cloned_service
                change.save()

        return new_environment

    def delete_resources(self):
        """
        delete all resources associated with this environment:
        services & their dependents
        """
        from .archived import ArchivedProject, ArchivedDockerService, ArchivedGitService

        archived_project = ArchivedProject.get_or_create_from_project(self.project)

        docker_service_list = (
            Service.objects.filter(Q(project=self.project) & Q(environment=self))
            .select_related("project", "healthcheck", "environment")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        )
        id_list = []
        for service in docker_service_list:
            if service.deployments.count() > 0:
                if service.type == Service.ServiceType.DOCKER_REGISTRY:
                    ArchivedDockerService.create_from_service(service, archived_project)
                else:
                    ArchivedGitService.create_from_service(service, archived_project)
                id_list.append(service.id)

        PortConfiguration.objects.filter(Q(service__id__in=id_list)).delete()
        URL.objects.filter(Q(service__id__in=id_list)).delete()
        Volume.objects.filter(Q(service__id__in=id_list)).delete()
        Config.objects.filter(Q(service__id__in=id_list)).delete()
        for service in docker_service_list:
            if service.healthcheck is not None:
                service.healthcheck.delete()

        if self.preview_metadata is not None:
            self.preview_metadata.delete()
        docker_service_list.delete()

    class Meta:
        indexes = [models.Index(fields=["name"])]
        unique_together = ["name", "project"]
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(name="production"),
                name="unique_production_per_project",
            )
        ]


class PreviewEnvTemplate(models.Model):
    id: int
    preview_metas: Manager["PreviewEnvMetadata"]
    variables: Manager["SharedTemplateEnvVariable"]

    class PreviewCloneStrategy(models.TextChoices):
        ALL = "ALL", _("All services")
        ONLY = "ONLY", _("Only specific services")

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="preview_templates"
    )
    slug = models.SlugField(max_length=100)
    base_environment = models.ForeignKey(
        Environment, null=True, on_delete=models.SET_NULL
    )
    clone_strategy = models.CharField(
        max_length=20,
        choices=PreviewCloneStrategy.choices,
        default=PreviewCloneStrategy.ALL,
    )
    services_to_clone = models.ManyToManyField(
        to=Service,
        related_name="preview_templates",
    )
    ttl_seconds = models.PositiveIntegerField(null=True)
    auto_teardown = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    preview_env_limit = models.PositiveIntegerField(
        default=5, validators=[MinValueValidator(1)]
    )
    preview_root_domain = models.CharField(
        max_length=1000,
        null=True,
        validators=[validate_url_domain],
    )
    auth_enabled = models.BooleanField(default=False)
    auth_user = models.CharField(null=True)
    auth_password = models.CharField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "project"], name="unique_template_name_per_project"
            ),
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(is_default=True),
                name="unique_default_template_per_project",
            ),
        ]


class SharedTemplateEnvVariable(BaseEnvVariable):
    ID_PREFIX = "env_tpl_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    template = models.ForeignKey(
        to=PreviewEnvTemplate, on_delete=models.CASCADE, related_name="variables"
    )

    class Meta:
        unique_together = ["key", "template"]


class SharedEnvVariable(BaseEnvVariable):
    ID_PREFIX = "env_prj_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    environment = models.ForeignKey(
        to=Environment, on_delete=models.CASCADE, related_name="variables"
    )

    class Meta:
        unique_together = ["key", "environment"]


class GitApp(TimestampedModel):
    ID_PREFIX = "git_con_"
    services: Manager["Service"]
    id = ShortUUIDField(
        length=16,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    github = models.OneToOneField(to=GitHubApp, on_delete=models.CASCADE, null=True)
    gitlab = models.OneToOneField(to=GitlabApp, on_delete=models.CASCADE, null=True)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(github__isnull=False) | Q(gitlab__isnull=False),
                name="github_or_gitlab_not_null",
            )
        ]
