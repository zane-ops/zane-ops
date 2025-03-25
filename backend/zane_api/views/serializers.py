import base64
from datetime import timedelta
from io import StringIO
import json
import re
import time
from typing import Any

import django_filters
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter
from dotenv import dotenv_values
from faker import Faker
from rest_framework import pagination
from rest_framework.request import Request

from ..dtos import DockerServiceSnapshot, DeploymentChangeDto

from .helpers import (
    compute_docker_service_snapshot,
    compute_docker_service_snapshot_with_changes,
    compute_all_deployment_changes,
)
from .. import serializers
from ..models import (
    URL,
    Deployment,
    Project,
    ArchivedProject,
    Service,
    Volume,
    EnvVariable,
    PortConfiguration,
    HttpLog,
    Config,
    DeploymentURL,
    DeploymentChange,
)
from ..temporal.helpers import (
    check_if_docker_image_exists,
    check_if_port_is_available_on_host,
    get_server_resource_limits,
)
from ..utils import (
    Colors,
    EnhancedJSONEncoder,
    convert_value_to_bytes,
    find_item_in_list,
    format_storage_value,
)
from ..git_client import GitClient
from ..validators import validate_url_path, validate_env_name

from search.dtos import RuntimeLogLevel, RuntimeLogSource
from search.serializers import RuntimeLogSerializer

# ==============================
#    Docker services create    #
# ==============================


class DockerCredentialsRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100, allow_blank=True, required=False)
    password = serializers.CharField(max_length=100, allow_blank=True, required=False)

    def validate(self, attrs: dict[str, str]):
        if attrs.get("username") and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "This field may not be blank."}
            )
        elif attrs.get("password") and not attrs.get("username"):
            raise serializers.ValidationError(
                {"username": "This field may not be blank."}
            )
        return attrs


class ServicePortsRequestSerializer(serializers.Serializer):
    host = serializers.IntegerField(required=True, min_value=1)
    forwarded = serializers.IntegerField(required=True, min_value=1)


class ConfigRequestSerializer(serializers.Serializer):
    contents = serializers.CharField(required=True, allow_blank=True)
    name = serializers.CharField(required=False)
    mount_path = serializers.URLPathField(required=True)
    language = serializers.CharField(default="plaintext", required=False)

    def validate(self, attrs: dict):
        if attrs.get("name") is None:
            fake = Faker()
            Faker.seed(time.monotonic())
            attrs["name"] = fake.slug().lower()
        return attrs


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, min_length=1)
    container_path = serializers.URLPathField(max_length=255)
    host_path = serializers.URLPathField(max_length=255, required=False, default=None)
    VOLUME_MODE_CHOICES = (
        ("READ_ONLY", _("READ_ONLY")),
        ("READ_WRITE", _("READ_WRITE")),
    )
    mode = serializers.ChoiceField(required=False, choices=VOLUME_MODE_CHOICES)

    def validate(self, attrs: dict):
        if attrs.get("mode") is None:
            if attrs.get("host_path") is not None:
                attrs["mode"] = "READ_ONLY"
            else:
                attrs["mode"] = "READ_WRITE"
        else:
            if attrs.get("host_path") is not None and attrs.get("mode") != "READ_ONLY":
                raise serializers.ValidationError(
                    {
                        "mode": [
                            f"Volumes with a host path can only be mounted in `read only` mode."
                        ]
                    }
                )
        if attrs.get("name") is None:
            fake = Faker()
            Faker.seed(time.monotonic())
            attrs["name"] = fake.slug().lower()
        return attrs


class URLRedirectSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)
    permanent = serializers.BooleanField(default=False)


class URLRequestSerializer(serializers.Serializer):
    domain = serializers.URLDomainField(required=False)
    base_path = serializers.URLPathField(required=False, default="/")
    strip_prefix = serializers.BooleanField(required=False, default=True)
    redirect_to = URLRedirectSerializer(required=False)
    associated_port = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs: dict):
        service: Service = self.context.get("service")  # type: ignore

        if attrs.get("domain") is None:
            attrs["domain"] = URL.generate_default_domain(service)

        if attrs["domain"] == settings.ZANE_APP_DOMAIN:
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where ZaneOps is installed is not allowed."
                    ]
                }
            )
        if attrs["domain"] == f"*.{settings.ZANE_APP_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where ZaneOps is installed as a wildcard domain is not allowed."
                    ]
                }
            )
        if attrs["domain"] == f"*.{settings.ROOT_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the root domain as a wildcard is not allowed as it would shadow all the other services installed on ZaneOps."
                    ]
                }
            )
        existing_urls = URL.objects.filter(
            Q(domain=attrs["domain"].lower())
            & Q(base_path=attrs["base_path"].lower())
            & ~Q(service__id=service.id if service is not None else None)
        ).distinct()
        if len(existing_urls) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{attrs['domain']}` and base path `{attrs['base_path']}` "
                        f"is already assigned to another service."
                    ]
                }
            )

        existing_deployment_urls = DeploymentURL.objects.filter(
            Q(domain=attrs["domain"].lower())
        ).distinct()
        if len(existing_deployment_urls) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{attrs['domain']}` is already assigned to another deployment."
                    ]
                }
            )

        domain = attrs["domain"]
        domain_parts = domain.split(".")
        domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)

        existing_parent_domain = URL.objects.filter(
            Q(domain=domain_as_wildcard.lower())
            & ~Q(service=service)
            & Q(base_path=attrs["base_path"].lower())
        ).distinct()
        if len(existing_parent_domain) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{attrs['domain']}` cannot be used because it will be shadowed by the wildcard"
                        f" domain `{domain_as_wildcard}` which is already assigned to another service."
                    ]
                }
            )

        if attrs.get("associated_port") is None and attrs.get("redirect_to") is None:
            raise serializers.ValidationError(
                {
                    "associated_port": [
                        f"To expose this service, you need to add an associated port to forward this URL to."
                    ]
                }
            )
        elif (
            attrs.get("associated_port") is not None
            and attrs.get("redirect_to") is not None
        ):
            raise serializers.ValidationError(
                {
                    "associated_port": [
                        f"You cannot provide an associated port if this URL is redirect URL."
                    ]
                }
            )

        return attrs


class MemoryLimitRequestSerializer(serializers.Serializer):
    MEMORY_UNITS = (
        ("BYTES", _("bytes")),
        ("KILOBYTES", _("kilobytes")),
        ("MEGABYTES", _("megabytes")),
        ("GIGABYTES", _("gigabytes")),
    )
    value = serializers.IntegerField(min_value=0)
    unit = serializers.ChoiceField(choices=MEMORY_UNITS, default="MEGABYTES")

    def validate(self, attrs: dict[str, int | str]):
        _, max_memory = get_server_resource_limits()
        six_megabytes = 6 * 1024 * 1024
        value_in_bytes = convert_value_to_bytes(int(attrs["value"]), attrs["unit"])  # type: ignore
        # The documentation for docker says that we can't use less than 6mb of memory :
        # https://docs.docker.com/engine/containers/resource_constraints/#limit-a-containers-access-to-memory
        if value_in_bytes < six_megabytes:
            raise serializers.ValidationError(
                {"value": "Cannot limit a service memory to less than 6 MiB."}
            )
        if value_in_bytes > max_memory:
            raise serializers.ValidationError(
                {
                    "value": f"The maximum memory limit on this server is {format_storage_value(max_memory)}."
                }
            )

        return attrs


class ResourceLimitsRequestSerializer(serializers.Serializer):
    cpus = serializers.FloatField(required=False, min_value=0.1)
    memory = MemoryLimitRequestSerializer(required=False)

    def validate(self, attrs: dict):
        max_cpus, _ = get_server_resource_limits()

        cpu_limit = attrs.get("cpus", 0)
        if cpu_limit > max_cpus:
            raise serializers.ValidationError(
                {"cpus": f"Cannot exceed {max_cpus} CPUs."}
            )

        return attrs


class HealthCheckRequestSerializer(serializers.Serializer):
    HEALTHCHECK_CHOICES = (
        ("PATH", _("path")),
        ("COMMAND", _("command")),
    )
    type = serializers.CustomChoiceField(required=True, choices=HEALTHCHECK_CHOICES)
    value = serializers.CharField(max_length=255, required=True)
    timeout_seconds = serializers.IntegerField(required=False, default=30, min_value=5)
    interval_seconds = serializers.IntegerField(required=False, default=30, min_value=5)
    associated_port = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs: dict):
        if attrs["type"] == "PATH":
            try:
                validate_url_path(attrs["value"])
            except ValidationError as e:
                raise serializers.ValidationError({"value": e.messages})

            if attrs.get("associated_port") is None:
                raise serializers.ValidationError(
                    {
                        "associated_port": "This field is required.",
                    }
                )
        else:
            if attrs.get("associated_port") is not None:
                raise serializers.ValidationError(
                    {
                        "associated_port": "Cannot specify an associated port for healthcheck of types `COMMAND`.",
                    }
                )

        return attrs


class EnvRequestSerializer(serializers.Serializer):
    key = serializers.CharField(required=True, validators=[validate_env_name])
    value = serializers.CharField(required=True, allow_blank=True)


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    image = serializers.CharField(required=True)
    credentials = DockerCredentialsRequestSerializer(required=False)

    def validate(self, attrs: dict):
        credentials = attrs.get("credentials")
        image = attrs["image"]

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=dict(credentials) if credentials is not None else None,
        )
        if not do_image_exists:
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` doesn't exist, or the provided credentials are invalid."
                        f" Did you forget to include the credentials?"
                    ]
                }
            )

        return attrs


# ==============================
#     Create Git services      #
# ==============================


class GitServiceCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    repository_url = serializers.URLField(required=True)
    branch_name = serializers.CharField(required=True)

    def validate(self, attrs: dict):
        repository_url = attrs["repository_url"]
        branch_name = attrs["branch_name"]
        client = GitClient()
        is_valid_repository = client.check_if_git_repository_is_valid(
            repository_url, branch_name
        )
        if not is_valid_repository:
            raise serializers.ValidationError(
                {
                    "repository_url": [
                        "The specified repository or branch may not or does not exist, or the repository could be private."
                    ]
                }
            )

        return attrs


class GitServiceDockerfileBuilderRequestSerializer(GitServiceCreateRequestSerializer):
    dockerfile_path = serializers.CharField(default="./Dockerfile")
    build_context_dir = serializers.CharField(default="./")
    builder = serializers.ChoiceField(
        choices=[Service.Builder.DOCKERFILE], default=Service.Builder.DOCKERFILE
    )


class GitServiceBuilderRequestSerializer(serializers.Serializer):
    builder = serializers.ChoiceField(
        choices=Service.Builder.choices, default=Service.Builder.DOCKERFILE
    )


# ==============================
#    Docker service deploy     #
# ==============================


class DockerServiceDeployRequestSerializer(serializers.Serializer):
    commit_message = serializers.CharField(required=False, allow_blank=True)


# ==============================
#    Git service deploy     #
# ==============================


class GitServiceDeployRequestSerializer(serializers.Serializer):
    ignore_build_cache = serializers.BooleanField(default=False)


# ====================================
#    Docker service webhook deploy   #
# ====================================


class DockerServiceWebhookDeployRequestSerializer(serializers.Serializer):
    commit_message = serializers.CharField(required=False, allow_blank=True)
    new_image = serializers.CharField(required=False)

    def validate_new_image(self, image: str | None):
        if image is None:
            return None

        service: Service | None = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=(
                dict(service.credentials) if service.credentials is not None else None
            ),
        )
        if not do_image_exists:
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` doesn't exist, or the credentials are invalid for this image."
                    ]
                }
            )

        return image


# ==============================
#       Docker deployments     #
# ==============================


class DockerServiceDeploymentFilterSet(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=Deployment.DeploymentStatus.choices
    )
    queued_at = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = Deployment
        fields = ["status", "queued_at"]


class DeploymentListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


# ==============================
#        Projects List         #
# ==============================


class ProjectListFilterSet(django_filters.FilterSet):
    sort_by = OrderingFilter(
        fields=["slug", "updated_at"],
        field_labels={
            "slug": "name",
        },
    )
    slug = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Project
        fields = ["slug"]


class ArchivedProjectListFilterSet(django_filters.FilterSet):
    sort_by = OrderingFilter(
        fields=["slug", "archived_at"],
        field_labels={
            "slug": "name",
        },
    )
    slug = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ArchivedProject
        fields = ["slug"]


class ProjectListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


# ==============================
#       Projects Create        #
# ==============================


class ProjectCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    description = serializers.CharField(required=False)


# ==============================
#       Projects Update        #
# ==============================


class ProjectUpdateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    description = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, str]):
        if not bool(attrs):
            raise serializers.ValidationError(
                "one of `slug` or `description` should be provided"
            )
        return attrs


# ==============================
#       Projects Search        #
# ==============================


class ProjectSearchSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    created_at = serializers.DateTimeField(required=True)
    slug = serializers.SlugField(required=True)
    type = serializers.ChoiceField(choices=["project"], default="project")


class ServiceSearchSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    project_slug = serializers.SlugField(required=True)
    slug = serializers.SlugField(required=True)
    created_at = serializers.DateTimeField(required=True)
    type = serializers.ChoiceField(choices=["service"], default="service")
    environment = serializers.CharField(required=True)


# ==============================
#       service Update         #
# ==============================


class DockerServiceUpdateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=True)


# ==============================
#    Docker services changes   #
# ==============================


class BaseChangeItemSerializer(serializers.Serializer):
    ITEM_CHANGE_TYPE_CHOICES = (
        ("ADD", _("Add")),
        ("DELETE", _("Delete")),
        ("UPDATE", _("Update")),
    )
    type = serializers.ChoiceField(choices=ITEM_CHANGE_TYPE_CHOICES, required=True)
    item_id = serializers.CharField(max_length=255, required=False)
    new_value = serializers.SerializerMethodField()
    field = serializers.SerializerMethodField()

    def get_service(self):
        service: Service | None = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")
        return service

    def get_new_value(self, obj):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )

    def get_field(self, obj: Any):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )

    def validate(self, attrs: dict[str, str | None]):
        item_id = attrs.get("item_id")
        change_type = attrs["type"]
        new_value = attrs.get("new_value")
        if change_type in ["DELETE", "UPDATE"]:
            if item_id is None:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            "`item_id` should be provided when the change type is `DELETE` or `UPDATE`"
                        ]
                    }
                )
        if change_type in ["ADD", "UPDATE"] and new_value is None:
            raise serializers.ValidationError(
                {
                    "new_value": [
                        "`new_value` should be provided when the change type is `ADD` or `UPDATE`"
                    ]
                }
            )
        if change_type == "DELETE":
            attrs["new_value"] = None
        if change_type == "ADD":
            attrs["item_id"] = None

        if attrs.get("item_id") is not None:
            service = self.get_service()
            changes = compute_all_deployment_changes(service, attrs)
            items_with_same_id = list(
                filter(
                    lambda c: c.item_id is not None
                    and c.item_id == attrs.get("item_id"),
                    changes,
                )
            )
            if len(items_with_same_id) >= 2:
                raise serializers.ValidationError(
                    {
                        "item_id": f"Cannot make conflicting changes for the field `{attrs['field']}` with id `{attrs.get('item_id')}`"
                        + "\nattempted to apply these changes :\n"
                        + "\n".join(
                            [
                                json.dumps(change, indent=2, cls=EnhancedJSONEncoder)
                                for change in items_with_same_id
                            ]
                        )
                    }
                )

        return attrs


class BaseFieldChangeSerializer(serializers.Serializer):
    FIELD_CHANGE_TYPE_CHOICES = (("UPDATE", _("Update")),)
    type = serializers.ChoiceField(
        choices=FIELD_CHANGE_TYPE_CHOICES, required=False, default="UPDATE"
    )
    new_value = serializers.SerializerMethodField()
    field = serializers.SerializerMethodField()

    def get_service(self):
        service: Service | None = self.context.get("service")  # type: ignore
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")
        return service

    def get_new_value(self, obj: Any):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )

    def get_field(self, obj: Any):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )


class URLItemChangeSerializer(BaseChangeItemSerializer):
    new_value = URLRequestSerializer(required=False)
    field = serializers.ChoiceField(choices=["urls"], required=True)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.urls.get(id=item_id)
            except URL.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"URL configuration item with id `{item_id}` does not exist for this service."
                        ]
                    }
                )

        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)
        # validate double host port
        new_value = attrs.get("new_value") or {}
        same_urls = list(
            filter(
                lambda url: url.domain is not None
                and url.base_path is not None
                and url.domain == new_value.get("domain")
                and url.base_path == new_value.get("base_path"),
                snapshot.urls,
            )
        )
        if len(same_urls) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "non_field_errors": "Duplicate urls values for the service are not allowed."
                    }
                }
            )

        if change_type == "ADD":
            domain = new_value["domain"]
            domain_parts = domain.split(".")
            domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)

            existing_parent_domain = URL.objects.filter(
                Q(domain=domain_as_wildcard.lower())
                & Q(base_path=new_value["base_path"].lower())
            ).distinct()
            if len(existing_parent_domain) > 0:
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "domain": [
                                f"Cannot add URL with domain `{domain}` as it will be shadowed by the wildcard"
                                + f" domain `{domain_as_wildcard}` which is already assigned."
                            ]
                        }
                    }
                )

        return attrs


class VolumeItemChangeSerializer(BaseChangeItemSerializer):
    new_value = VolumeRequestSerializer(required=False)
    field = serializers.ChoiceField(choices=["volumes"], required=True)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        new_value = attrs.get("new_value") or {}
        current_volume: Volume | None = None
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                current_volume = service.volumes.get(id=item_id)
            except Volume.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Volume with id `{item_id}` does not exist for this service."
                        ]
                    }
                )

        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)

        # validate double container paths
        volumes_with_same_container_path = list(
            filter(
                lambda v: v.container_path is not None
                and v.container_path == new_value.get("container_path"),
                snapshot.volumes,
            )
        )
        if len(volumes_with_same_container_path) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "container_path": "Cannot specify two volumes with the same `container path` for this service."
                    }
                }
            )

        # validate double host path
        volumes_with_same_host_path = list(
            filter(
                lambda v: v.host_path is not None
                and v.host_path == new_value.get("host_path"),
                snapshot.volumes,
            )
        )

        if len(volumes_with_same_host_path) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host_path": "Cannot specify two volumes with the same `host path` for this service."
                    }
                }
            )

        # check if host path is not already used by another service
        if new_value.get("host_path") is not None:
            already_existing_volumes = Volume.objects.filter(
                Q(host_path__isnull=False)
                & Q(host_path=new_value.get("host_path"))
                & ~Q(service__id=service.id)
            ).values("mode")
            if len(already_existing_volumes) > 0:
                mode_set = {volume["mode"] for volume in already_existing_volumes}
                if (
                    new_value.get("mode") != Volume.VolumeMode.READ_ONLY
                    or Volume.VolumeMode.READ_WRITE in mode_set
                ):
                    raise serializers.ValidationError(
                        {
                            "new_value": {
                                "host_path": f"Another service is already using the host path"
                                f" `{new_value.get('host_path')}`."
                                f" To share the same host path between two services, both must be mounted in READ_ONLY mode."
                            }
                        }
                    )
        if change_type == "UPDATE" and current_volume is not None:
            if (
                new_value.get("host_path") is None
                and current_volume.host_path is not None
            ):
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "host_path": f"Cannot remove the host path from a volume that was originally mounted with one, "
                            f"you need to delete and recreate the volume without the host path."
                        }
                    }
                )

            if (
                new_value.get("host_path") is not None
                and current_volume.host_path is None
            ):
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "host_path": f"Cannot mount a volume to a host path if it wasn't originally mounted that way, "
                            f"you need to delete and recreate the volume with a host path."
                        }
                    }
                )

        return attrs


class ConfigItemChangeSerializer(BaseChangeItemSerializer):
    field = serializers.ChoiceField(choices=["configs"], required=True)
    new_value = ConfigRequestSerializer(required=False)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        new_value = attrs.get("new_value") or {}

        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.configs.get(id=item_id)
            except Config.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Config file with id `{item_id}` does not exist for this service."
                        ]
                    }
                )
        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)

        # validate double container paths
        config_with_same_path = list(
            filter(
                lambda c: c.mount_path == new_value.get("mount_path"),
                snapshot.configs,
            )
        )

        if len(config_with_same_path) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "mount_path": "Cannot specify two config files with the same `mount path` for this service."
                    }
                }
            )

        volume_with_same_container_path = find_item_in_list(
            lambda v: v.container_path == new_value.get("mount_path"),
            snapshot.volumes,
        )
        if volume_with_same_container_path is not None:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "mount_path": "Another volume is already attached on the same path in this service."
                    }
                }
            )

        return attrs


class EnvItemChangeSerializer(BaseChangeItemSerializer):
    new_value = EnvRequestSerializer(required=False)
    field = serializers.ChoiceField(choices=["env_variables"], required=True)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        new_value = attrs.get("new_value") or {}
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.env_variables.get(id=item_id)  # type: ignore
            except EnvVariable.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Env variable with id `{item_id}` does not exist for this service."
                        ]
                    }
                )

        # validate double `key`
        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)
        if new_value is not None:
            envs_with_same_key = list(
                filter(
                    lambda env: env.key is not None and env.key == new_value.get("key"),
                    snapshot.env_variables,
                )
            )

            if len(envs_with_same_key) >= 2:
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "key": "Cannot specify two env variables with the same name for this service"
                        }
                    }
                )
        return attrs


class PortItemChangeSerializer(BaseChangeItemSerializer):
    field = serializers.ChoiceField(choices=["ports"], required=True)
    new_value = ServicePortsRequestSerializer(required=False)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        new_value = attrs.get("new_value") or {}
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.ports.get(id=item_id)
            except PortConfiguration.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Port configuration item with id `{item_id}` does not exist for this service."
                        ]
                    }
                )

        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)

        # validate double host port
        ports_with_same_host = list(
            filter(
                lambda port: port.host is not None
                and port.host == new_value.get("host"),
                snapshot.ports,
            )
        )
        if len(ports_with_same_host) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": "Duplicate `host` port values for the service are not allowed."
                    }
                }
            )

        # do not allow for binding to http
        if len(snapshot.http_ports) > 0:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": "You cannot expose a service to the HTTP output (80/443),"
                        " please add an URL if you want to expose your app to the internet."
                    }
                }
            )

        # check if port is available
        public_port = new_value.get("host")

        # check if port is not already used by another service
        already_existing_port = PortConfiguration.objects.filter(
            Q(host=public_port) & ~Q(service=service)
        ).first()
        if already_existing_port is not None:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": f"host Port `{already_existing_port.host}` is already used by another service."
                    }
                }
            )

        if public_port is not None and not check_if_port_is_available_on_host(
            public_port
        ):
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": f"Port `{public_port}` is not available on the host machine."
                    }
                }
            )

        return attrs


class ResourceLimitChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["resource_limits"], required=True)
    new_value = ResourceLimitsRequestSerializer(required=True, allow_null=True)


class DockerSourceRequestSerializer(serializers.Serializer):
    image = serializers.CharField(required=True)
    credentials = DockerCredentialsRequestSerializer(required=False)

    def validate(self, attrs: dict):
        image: str = attrs["image"]
        credentials: dict | None = attrs.get("credentials")
        if credentials is not None and (
            len(credentials) == 0
            or (not credentials.get("username") and not credentials.get("password"))
        ):
            credentials = None

        do_image_exists = check_if_docker_image_exists(
            image, credentials=dict(credentials) if credentials is not None else None
        )
        if not do_image_exists:
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` doesn't exist, or the provided credentials are invalid."
                        f" Did you forget to include the credentials?"
                    ]
                }
            )
        return attrs


class DockerSourceFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["source"], required=True)
    new_value = DockerSourceRequestSerializer(required=True)


class DockerCommandFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["command"], required=True)
    new_value = serializers.CharField(required=True, allow_null=True)


class HealthcheckFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["healthcheck"], required=True)
    new_value = HealthCheckRequestSerializer(required=True, allow_null=True)


class DockerDeploymentFieldChangeRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        required=True,
        choices=[
            "source",
            "urls",
            "volumes",
            "env_variables",
            "ports",
            "command",
            "healthcheck",
            "resource_limits",
            "configs",
        ],
    )


# ==============================
#       Collect Logs           #
# ==============================


class DockerContainerLogSerializer(serializers.Serializer):
    log = serializers.CharField(required=True, allow_blank=True, trim_whitespace=False)
    container_id = serializers.CharField(required=True)
    container_name = serializers.CharField(required=True)
    time = serializers.CharField(required=True)
    tag = serializers.CharField(required=True)
    SOURCES = (
        ("stdout", _("standard ouput")),
        ("stderr", _("standard error")),
    )
    source = serializers.ChoiceField(choices=SOURCES, required=True)


class HTTPServiceRequestSerializer(serializers.Serializer):
    remote_ip = serializers.IPAddressField(required=True)
    client_ip = serializers.IPAddressField(required=True)
    remote_port = serializers.CharField(required=True)
    PROTOCOLS = [
        ("HTTP/1.0", "HTTP/1.0"),
        ("HTTP/1.1", "HTTP/1.1"),
        ("HTTP/2.0", "HTTP/2.0"),
        ("HTTP/3.0", "HTTP/3.0"),
    ]
    REQUEST_METHODS = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("DELETE", "DELETE"),
        ("PATCH", "PATCH"),
        ("OPTIONS", "OPTIONS"),
        ("HEAD", "HEAD"),
    ]
    proto = serializers.ChoiceField(choices=PROTOCOLS, required=True)
    method = serializers.ChoiceField(choices=REQUEST_METHODS, required=True)
    host = serializers.CharField(required=True)
    uri = serializers.CharField(required=True)
    headers = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=True,
    )


class HTTPServiceLogSerializer(serializers.Serializer):
    ts = serializers.FloatField(required=True)
    msg = serializers.CharField(required=True)
    LOG_LEVELS = (
        ("debug", _("debug")),
        ("info", _("info")),
        ("warn", _("warn")),
        ("error", _("error")),
        ("panic", _("panic")),
        ("fatal", _("fatal")),
    )
    level = serializers.ChoiceField(choices=LOG_LEVELS, required=True)

    duration = serializers.FloatField()
    status = serializers.IntegerField(min_value=100)
    resp_headers = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )
    request = HTTPServiceRequestSerializer()
    zane_deployment_upstream = serializers.CharField()
    zane_deployment_green_hash = serializers.CharField(
        allow_null=True, required=False, allow_blank=True
    )
    zane_deployment_blue_hash = serializers.CharField(
        allow_null=True, required=False, allow_blank=True
    )
    zane_service_id = serializers.CharField()
    uuid = serializers.CharField(allow_null=True, required=False, allow_blank=True)


class DockerContainerLogsRequestSerializer(serializers.ListSerializer):
    child = DockerContainerLogSerializer()


class DockerContainerLogsResponseSerializer(serializers.Serializer):
    simple_logs_inserted = serializers.IntegerField(min_value=0)
    http_logs_inserted = serializers.IntegerField(min_value=0)


# ==============================
#      Deployment Logs         #
# ==============================


class DeploymentLogsQuerySerializer(serializers.Serializer):
    time_before = serializers.DateTimeField(required=False)
    time_after = serializers.DateTimeField(required=False)
    query = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    source = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[RuntimeLogSource.SERVICE, RuntimeLogSource.SYSTEM]
        ),
        required=False,
    )
    level = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[RuntimeLogLevel.INFO, RuntimeLogLevel.ERROR]
        ),
        required=False,
    )
    per_page = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=50
    )
    cursor = serializers.CharField(required=False)

    def validate_cursor(self, cursor: str):
        try:
            decoded_data = base64.b64decode(cursor, validate=True)
            decoded_string = decoded_data.decode("utf-8")
            serializer = CursorSerializer(data=json.loads(decoded_string))
            serializer.is_valid(raise_exception=True)
        except (serializers.ValidationError, ValueError):
            raise serializers.ValidationError(
                {
                    "cursor": "Invalid cursor format, it should be a base64 encoded string of a JSON object."
                }
            )
        return cursor


class CursorSerializer(serializers.Serializer):
    sort = serializers.ListField(required=True, child=serializers.CharField())
    order = serializers.ChoiceField(choices=["desc", "asc"], required=True)


class DeploymentHttpLogsPagination(pagination.CursorPagination):
    page_size = 50
    page_size_query_param = "per_page"
    ordering = ("-time",)

    def get_ordering(self, request: Request, queryset, view):
        filter = DeploymentHttpLogsFilterSet(
            {"sort_by": ",".join(request.GET.getlist("sort_by"))}
        )

        if filter.is_valid():
            ordering = tuple(
                set(filter.form.cleaned_data.get("sort_by", self.ordering))
            )
            if len(ordering) > 0:
                return ordering  # tuple(set(filter.form.cleaned_data.get("sort_by", self.ordering)))

        return self.ordering


class DeploymentHttpLogsFilterSet(django_filters.FilterSet):
    time = django_filters.DateTimeFromToRangeFilter()
    request_method = django_filters.MultipleChoiceFilter(
        choices=HttpLog.RequestMethod.choices
    )
    sort_by = OrderingFilter(fields=["time", "request_duration_ns"])
    request_query = django_filters.CharFilter(
        field_name="request_query", method="filter_query"
    )
    status = django_filters.BaseInFilter(method="filter_multiple_values")
    request_ip = django_filters.BaseInFilter(method="filter_multiple_values")
    request_user_agent = django_filters.BaseInFilter(method="filter_multiple_values")
    request_host = django_filters.BaseInFilter(
        field_name="request_host", method="filter_multiple_values"
    )
    request_path = django_filters.BaseInFilter(method="filter_multiple_values")

    def filter_multiple_values(self, queryset: QuerySet, name: str, value: str):
        params = self.request.GET.getlist(name)  # type: ignore

        status_prefix_path = r"^\dxx$"

        queries = Q()
        if name == "status":
            for param in params:
                if re.match(status_prefix_path, param):
                    prefix = int(param[0])
                    queries = queries | (
                        Q(status__gte=(prefix * 100), status__lte=(prefix * 100) + 99)
                    )
                elif re.match(r"^\d+$", param):
                    queries = queries | Q(status=int(param))
        else:
            queries = Q(**{f"{name}__in": params})
        print(f"Query: {Colors.GREY}{queries}{Colors.ENDC}")
        return queryset.filter(queries)

    def filter_query(self, queryset: QuerySet, name: str, value: str):
        return queryset.filter(request_query__istartswith=value)

    class Meta:
        model = HttpLog
        fields = [
            "time",
            "request_method",
            "request_path",
            "request_host",
            "request_query",
            "status",
            "request_ip",
            "request_id",
            "request_user_agent",
        ]


# ==============================
#       Http logs fields       #
# ==============================


class HttpLogFieldsQuerySerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        choices=[
            "request_host",
            "request_path",
            "request_user_agent",
            "request_ip",
        ]
    )
    value = serializers.CharField(allow_blank=True)


class HttpLogFieldsResponseSerializer(serializers.ListSerializer):
    child = serializers.CharField()


# ==============================
#     Project Service List     #
# ==============================


class ServiceListParamSerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


class BaseServiceCardSerializer(serializers.Serializer):
    updated_at = serializers.DateTimeField(required=True)
    volume_number = serializers.IntegerField(required=True)
    slug = serializers.CharField(required=True)
    url = serializers.URLField(allow_null=True)
    STATUS_CHOICES = (
        ("HEALTHY", _("Healthy")),
        ("UNHEALTHY", _("Unhealthy")),
        ("FAILED", _("Failed")),
        ("SLEEPING", _("Sleeping")),
        ("NOT_DEPLOYED_YET", _("Not deployed yet")),
        ("DEPLOYING", _("Deploying")),
    )
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    id = serializers.CharField(required=True)


class DockerServiceCardSerializer(BaseServiceCardSerializer):
    type = serializers.ChoiceField(choices=["docker"], default="docker")
    image = serializers.CharField(required=True)
    tag = serializers.CharField(required=True)


class GitServiceCardSerializer(BaseServiceCardSerializer):
    type = serializers.ChoiceField(choices=["git"], default="git")
    repository = serializers.CharField(required=True)
    last_commit_message = serializers.CharField(required=False)
    branch = serializers.CharField(required=True)


# ==============================
#       Resources Search       #
# ==============================


class ResourceSearchParamSerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


# =============================================
#       Load env variables as big string      #
# =============================================


class EnvStringChangeSerializer(serializers.Serializer):
    new_value = serializers.CharField(required=True, allow_blank=True)

    def validate(self, attrs: dict):
        service: Service | None = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")

        envs = dotenv_values(stream=StringIO(attrs["new_value"]))
        errors = []
        for key, value in envs.items():
            try:
                validate_env_name(key)
            except ValidationError as err:
                errors.append(f"`{key}` is not a valid variable name : {err.message}")

            if value is None:
                envs[key] = ""
        if len(errors) > 0:
            raise serializers.ValidationError({"new_value": errors})

        new_value = ""
        for key, value in envs.items():
            new_value += f"{key}='{value}'\n"
        attrs["new_value"] = new_value

        # validate double `key`
        env_changes = [
            DeploymentChangeDto(
                type="ADD",
                field=DeploymentChange.ChangeField.ENV_VARIABLES,
                new_value={
                    "key": key,
                    "value": value,
                },
            )
            for key, value in envs.items()
        ]
        snapshot = compute_docker_service_snapshot(
            DockerServiceSnapshot.from_dict(
                serializers.ServiceSerializer(service).data  # type: ignore
            ),
            [*env_changes, *compute_all_deployment_changes(service)],
        )

        for env in snapshot.duplicate_envs:
            errors.append(f"variable with name `{env}` already exists in the service")

        if len(errors) > 0:
            raise serializers.ValidationError({"new_value": errors})

        return attrs


# ==========================================
#       Service & deployment metrics       #
# ==========================================


class ServiceMetricsSerializer(serializers.Serializer):
    bucket_epoch = serializers.DateTimeField()
    avg_cpu = serializers.FloatField()
    avg_memory = serializers.FloatField()
    total_net_tx = serializers.IntegerField()
    total_net_rx = serializers.IntegerField()
    total_disk_read = serializers.IntegerField()
    total_disk_write = serializers.IntegerField()


class ServiceMetricsResponseSerializer(serializers.ListSerializer):
    child = ServiceMetricsSerializer()


class ServiceMetricsQuery(serializers.Serializer):
    time_range = serializers.ChoiceField(
        choices=["LAST_HOUR", "LAST_6HOURS", "LAST_DAY", "LAST_WEEK", "LAST_MONTH"],
        required=False,
        default="LAST_HOUR",
    )


# ==========================================
#              User Creation               #
# ==========================================


class UserExistenceResponseSerializer(serializers.Serializer):
    exists = serializers.BooleanField()


class UserCreationRequestSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=1, max_length=255)
    password = serializers.CharField(min_length=8)


class UserCreatedResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


# ==========================================
#       AUTO UPDATE DOCKER SERVICES        #
# ==========================================


class AutoUpdateRequestSerializer(serializers.Serializer):
    desired_version = serializers.CharField(required=True, max_length=255)


class AutoUpdateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


# ==========================================
#               Environments               #
# ==========================================


class CreateEnvironmentRequestSerializer(serializers.Serializer):
    name = serializers.SlugField(max_length=255)


class CloneEnvironmentRequestSerializer(serializers.Serializer):
    deploy_services = serializers.BooleanField(default=False, required=False)
    name = serializers.SlugField(max_length=255)


# ==========================================
#         Toggle Service state             #
# ==========================================


class ToggleServiceStateRequestSerializer(serializers.Serializer):
    desired_state = serializers.ChoiceField(choices=["start", "stop"])


class BulkToggleServiceStateRequestSerializer(serializers.Serializer):
    desired_state = serializers.ChoiceField(choices=["start", "stop"])
    service_ids = serializers.ListField(child=serializers.CharField())
