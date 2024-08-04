import dataclasses
import json
from typing import Any

import django_filters
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter
from rest_framework import pagination

from .helpers import (
    compute_docker_service_snapshot_with_changes,
    compute_all_deployment_changes,
)
from .. import serializers
from ..docker_operations import (
    check_if_docker_image_exists,
    check_if_port_is_available_on_host,
)
from ..models import (
    URL,
    DockerDeployment,
    Project,
    ArchivedProject,
    DockerRegistryService,
    Volume,
    DockerEnvVariable,
    PortConfiguration,
    SimpleLog,
    HttpLog,
)
from ..utils import EnhancedJSONEncoder
from ..validators import validate_url_path, validate_env_name


# ==============================
#    Docker services create    #
# ==============================


class DockerCredentialsRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100, allow_blank=True, required=False)
    password = serializers.CharField(max_length=100, allow_blank=True, required=False)


class ServicePortsRequestSerializer(serializers.Serializer):
    host = serializers.IntegerField(required=False, default=80)
    forwarded = serializers.IntegerField(required=True)


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, min_length=1)
    container_path = serializers.CharField(max_length=255)
    host_path = serializers.URLPathField(max_length=255, required=False, default=None)
    VOLUME_MODE_CHOICES = (
        ("READ_ONLY", _("READ_ONLY")),
        ("READ_WRITE", _("READ_WRITE")),
    )
    mode = serializers.ChoiceField(
        required=False, choices=VOLUME_MODE_CHOICES, default="READ_WRITE"
    )


class URLRequestSerializer(serializers.Serializer):
    domain = serializers.URLDomainField(required=True)
    base_path = serializers.URLPathField(required=False, default="/")
    strip_prefix = serializers.BooleanField(required=False, default=True)

    def validate(self, url: dict[str, str]):
        service: DockerRegistryService = self.context.get("service")
        if url["domain"] == settings.ZANE_APP_DOMAIN:
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where ZaneOps is installed is not allowed."
                    ]
                }
            )
        if url["domain"] == f"*.{settings.ZANE_APP_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where ZaneOps is installed as a wildcard domain is not allowed."
                    ]
                }
            )
        if url["domain"] == f"*.{settings.ROOT_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the root domain as a wildcard is not allowed as it would shadow all the other services installed on ZaneOps."
                    ]
                }
            )
        existing_urls = URL.objects.filter(
            Q(domain=url["domain"].lower())
            & Q(base_path=url["base_path"].lower())
            & ~Q(dockerregistryservice__id=service.id if service is not None else None)
        ).distinct()
        if len(existing_urls) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{url['domain']}` and base path `{url['base_path']}` "
                        f"is already assigned to another service."
                    ]
                }
            )

        domain = url["domain"]
        domain_parts = domain.split(".")
        domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)

        existing_parent_domain = URL.objects.filter(
            domain=domain_as_wildcard.lower()
        ).distinct()
        if len(existing_parent_domain) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{url['domain']}` cannot be used because it will be shadowed by the wildcard"
                        f" domain `{domain_as_wildcard}` which is already assigned to another service."
                    ]
                }
            )

        return url


class HealthCheckRequestSerializer(serializers.Serializer):
    HEALTCHECK_CHOICES = (
        ("PATH", _("path")),
        ("COMMAND", _("command")),
    )
    type = serializers.ChoiceField(required=True, choices=HEALTCHECK_CHOICES)
    value = serializers.CharField(max_length=255, required=True)
    timeout_seconds = serializers.IntegerField(required=False, default=30, min_value=5)
    interval_seconds = serializers.IntegerField(required=False, default=30, min_value=5)

    def validate(self, data: dict):
        if data["type"] == "PATH":
            try:
                validate_url_path(data["value"])
            except ValidationError as e:
                raise serializers.ValidationError({"value": e.messages})
        return data


class EnvRequestSerializer(serializers.Serializer):
    key = serializers.CharField(required=True, validators=[validate_env_name])
    value = serializers.CharField(required=True)


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    image = serializers.CharField(required=True)
    credentials = DockerCredentialsRequestSerializer(required=False)

    def validate(self, data: dict):
        credentials = data.get("credentials")
        image = data.get("image")

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=dict(credentials) if credentials is not None else None,
        )
        if not do_image_exists:
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` does not exist or the credentials are invalid for this image."
                        f" Have you forgotten to include the credentials ?"
                    ]
                }
            )

        return data


# ==============================
#       Docker deployments     #
# ==============================


class DockerServiceDeploymentFilterSet(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=DockerDeployment.DeploymentStatus.choices
    )
    created_at = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = DockerDeployment
        fields = ["status", "created_at"]


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
        service: DockerRegistryService | None = self.context.get("service")
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
        service: DockerRegistryService = self.context.get("service")
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
                    "new_value": "Duplicate urls values for the service are not allowed."
                    + "\nthese urls conflicts :\n"
                    + "\n".join(
                        [
                            json.dumps(url, indent=2, cls=EnhancedJSONEncoder)
                            for url in same_urls
                        ]
                    )
                }
            )

        http_ports = [80, 443]
        if len(snapshot.urls) > 0:
            for port in snapshot.ports:
                if port.host not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "new_value": f"Cannot specify both a custom URL and a port with `host` other than a HTTP port (80/443)"
                        }
                    )

        if (
            change_type == "DELETE"
            and snapshot.healthcheck is not None
            and snapshot.healthcheck.type == "PATH"
        ):
            if len(snapshot.urls) == 0 and len(snapshot.http_ports) == 0:
                raise serializers.ValidationError(
                    {
                        "new_value": f"Cannot delete an URL if there is a path healthcheck attached to it"
                        f" and the service is not exposed to the public through a port with a HTTP `host` (80/443)"
                    }
                )

        if change_type == "ADD" and len(snapshot.http_ports) == 0:
            raise serializers.ValidationError(
                {
                    "new_value": f"adding an URL requires that one port with a HTTP `host` (80/443) is set in the service."
                }
            )

        return attrs


class VolumeItemChangeSerializer(BaseChangeItemSerializer):
    new_value = VolumeRequestSerializer(required=False)
    field = serializers.ChoiceField(choices=["volumes"], required=True)

    def validate(self, change: dict):
        super().validate(change)
        service = self.get_service()
        change_type = change["type"]
        new_value = change.get("new_value") or {}
        current_volume: Volume | None = None
        if change_type in ["DELETE", "UPDATE"]:
            item_id = change["item_id"]

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

        snapshot = compute_docker_service_snapshot_with_changes(service, change)

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
            already_existing_volumes: Volume | None = Volume.objects.filter(
                Q(host_path__isnull=False)
                & Q(host_path=new_value.get("host_path"))
                & ~Q(dockerregistryservice__id=service.id)
            ).first()
            if already_existing_volumes is not None:
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "host_path": f"Another service is already mounted to the host path `{already_existing_volumes.host_path}`."
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
                            "host_path": f"Cannot set the `host path` of a volume mounted to one to null, "
                            f"you need to delete and recreate the volume without a host path instead."
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
                            "host_path": f"Cannot mount a volume to host path if it wasn't mounted to one before, "
                            f"you need to delete and recreate the volume with a host path instead."
                        }
                    }
                )

        return change


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
                service.env_variables.get(id=item_id)
            except DockerEnvVariable.DoesNotExist:
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
                            "key": "Cannot specify two env variables with the same `key` for this service"
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
                        "host": "Duplicate `host` port values are not allowed."
                        + "\nthese ports conflicts :\n"
                        + "\n".join(
                            [
                                json.dumps(port, indent=2, cls=EnhancedJSONEncoder)
                                for port in ports_with_same_host
                            ]
                        )
                    }
                }
            )

        # validate double http port
        if len(snapshot.http_ports) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": "Only one HTTP `host` port (80/443) is allowed,"
                        " we cannot forward the http requests to two distinct ports."
                    }
                }
            )

        # validate that url & host ports don't clash
        http_ports = [80, 443]
        if len(snapshot.urls) > 0:
            for port in snapshot.ports:
                if port.host not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "new_value": {
                                "host": f"Cannot specify both a custom URL and a `host` port other than a HTTP port (80/443)"
                            }
                        }
                    )

        # check if port is available
        public_port = new_value.get("host")
        if public_port is not None and public_port not in http_ports:
            is_port_available = check_if_port_is_available_on_host(public_port)
            if not is_port_available:
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "host": f"Port `{public_port}` is not available on the host machine."
                        }
                    }
                )

        # check if port is not already used by another service
        already_existing_port: PortConfiguration = PortConfiguration.objects.filter(
            Q(host=public_port)
            & Q(host__isnull=False)
            & ~Q(dockerregistryservice=service)
        ).first()
        if already_existing_port is not None:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": f"host Port `{already_existing_port.host}` is already used by another service."
                    }
                }
            )

        if (
            change_type == "DELETE"
            and snapshot.healthcheck is not None
            and snapshot.healthcheck.type == "PATH"
        ):
            if len(snapshot.urls) == 0 and len(snapshot.http_ports) == 0:
                raise serializers.ValidationError(
                    {
                        "new_value": f"Cannot delete a PORT if there is a path healthcheck attached to it "
                        f"and the service is not exposed to the public through an URL or a port with a `host` HTTP (80/443)"
                    }
                )

        return attrs


class DockerCredentialsFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["credentials"], required=True)
    new_value = DockerCredentialsRequestSerializer(required=True, allow_null=True)

    def validate(self, attrs: dict):
        service = self.get_service()
        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)

        if snapshot.credentials is not None:
            do_image_exists = check_if_docker_image_exists(
                snapshot.image,
                credentials=dataclasses.asdict(snapshot.credentials),
            )
            if not do_image_exists:
                raise serializers.ValidationError(
                    {
                        "new_value": f"The credentials are invalid for the image `{snapshot.image}` set in the service."
                    }
                )
        return attrs


class DockerCommandFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["command"], required=True)
    new_value = serializers.CharField(required=True, allow_null=True)


class DockerImageFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["image"], required=True)
    new_value = serializers.CharField(required=True, min_length=1)

    def validate(self, attrs: dict):
        service = self.get_service()
        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)

        if snapshot.credentials is not None:
            do_image_exists = check_if_docker_image_exists(
                snapshot.image,
                credentials=dataclasses.asdict(snapshot.credentials),
            )
            if not do_image_exists:
                raise serializers.ValidationError(
                    {
                        "new_value": f"The credentials are invalid for the image `{snapshot.image}` provided for the service."
                    }
                )
        return attrs


class HealthcheckFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["healthcheck"], required=True)
    new_value = HealthCheckRequestSerializer(required=True, allow_null=True)

    def validate(self, attrs: dict):
        service = self.get_service()
        snapshot = compute_docker_service_snapshot_with_changes(service, attrs)

        new_healthcheck = attrs.get("new_value")
        if new_healthcheck is not None and new_healthcheck.get("type") == "PATH":
            if len(snapshot.urls) == 0 and len(snapshot.http_ports) == 0:
                raise serializers.ValidationError(
                    {
                        "new_value": f"healthcheck requires that at least one `url`"
                        f" or one port with a HTTP `host` (80/443) is set in the service."
                    }
                )
        return attrs


class DockerDeploymentFieldChangeRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        required=True,
        choices=[
            "urls",
            "volumes",
            "env_variables",
            "ports",
            "credentials",
            "command",
            "image",
            "healthcheck",
        ],
    )


# ==============================
#       Collect Logs           #
# ==============================


class DockerContainerLogSerializer(serializers.Serializer):
    log = serializers.CharField(required=True, allow_blank=True)
    container_id = serializers.CharField(required=True)
    container_name = serializers.CharField(required=True)
    time = serializers.DateTimeField(required=True)
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


class DeploymentLogsFilterSet(django_filters.FilterSet):
    time = django_filters.DateTimeFromToRangeFilter()
    content = django_filters.CharFilter(method="filter_content")

    def filter_content(self, queryset: QuerySet, name: str, value: str):
        # construct the full lookup expression.
        lookup = f"{name}__icontains"
        return queryset.filter(**{lookup: value.replace('"', '\\"')})

    class Meta:
        model = SimpleLog
        fields = ["level", "content", "time"]


class DeploymentLogsPagination(pagination.CursorPagination):
    page_size = 50
    page_size_query_param = "per_page"
    ordering = "-time"


class DeploymentHttpLogsFilterSet(django_filters.FilterSet):
    time = django_filters.DateTimeFromToRangeFilter()
    request_method = django_filters.MultipleChoiceFilter(
        choices=HttpLog.RequestMethod.choices
    )

    class Meta:
        model = HttpLog
        fields = [
            "time",
            "request_method",
            "request_path",
            "request_host",
            "status",
            "request_ip",
        ]


# ==============================
#         Proxy Logs           #
# ==============================


class ProxyLogsFilterSet(django_filters.FilterSet):
    time = django_filters.DateTimeFromToRangeFilter()
    content = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SimpleLog
        fields = ["level", "content", "time"]


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
        ("SLEEPING", _("Sleeping")),
        ("NOT_DEPLOYED_YET", _("Not deployed yet")),
        ("DEPLOYING", _("Deploying")),
        ("CANCELLED", _("Cancelled")),
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
