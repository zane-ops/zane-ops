import dataclasses
import json
from typing import Any

import django_filters
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter
from rest_framework import pagination

from .helpers import (
    compute_docker_service_snapshot_from_changes,
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
)
from ..utils import EnhancedJSONEncoder
from ..validators import validate_url_path, validate_env_name


# ==============================
#    Docker services create    #
# ==============================


class DockerCredentialsRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)


class ServicePortsRequestSerializer(serializers.Serializer):
    host = serializers.IntegerField(required=False, default=80)
    forwarded = serializers.IntegerField(required=True)


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    container_path = serializers.CharField(max_length=255)
    host_path = serializers.URLPathField(max_length=255, required=False)
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
        if url["domain"] == settings.ZANE_APP_DOMAIN:
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where zaneOps is installed is not allowed."
                    ]
                }
            )
        if url["domain"] == f"*.{settings.ZANE_APP_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where zaneOps is installed as a wildcard domain is not allowed."
                    ]
                }
            )
        existing_urls = URL.objects.filter(
            domain=url["domain"].lower(), base_path=url["base_path"].lower()
        ).distinct()
        if len(existing_urls) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"""URL with domain `{url['domain']}` and base path `{url['base_path']}` """
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
    timeout_seconds = serializers.IntegerField(required=False, default=60, min_value=5)
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
    command = serializers.CharField(required=False)
    urls = URLRequestSerializer(many=True, required=False, default=[])
    ports = ServicePortsRequestSerializer(required=False, many=True, default=[])
    env = serializers.DictField(child=serializers.CharField(), required=False)
    volumes = VolumeRequestSerializer(many=True, required=False, default=[])
    healthcheck = HealthCheckRequestSerializer(required=False)

    def validate(self, data: dict):
        credentials = data.get("credentials")
        image = data.get("image")
        healthcheck = data.get("healthcheck")

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

        urls = data.get("urls", [])
        ports = data.get("ports", [])

        http_ports = [80, 443]
        if len(urls) > 0:
            for port in ports:
                if port["host"] not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "urls": [
                                f"Cannot specify both a custom URL and a host port other than a HTTP port (80/443)"
                            ]
                        }
                    )

        if healthcheck is not None and healthcheck["type"].lower() == "path":
            if len(ports) == 0 and len(urls) == 0:
                raise serializers.ValidationError(
                    {
                        "healthcheck": {
                            "path": [
                                f"healthcheck requires that at least one `url` or one `port` is provided"
                            ]
                        }
                    }
                )
        return data

    def validate_ports(self, ports: list[dict[str, int]]):
        no_of_http_ports = 0
        http_ports = [80, 443]
        public_ports_seen = set()
        for port in ports:
            public_port = port["host"]

            # Check for only 1 http port
            if public_port in http_ports:
                no_of_http_ports += 1
            if no_of_http_ports > 1:
                raise serializers.ValidationError("Only one HTTP port is allowed")

            # Check for duplicate public ports
            if public_port in public_ports_seen:
                raise serializers.ValidationError(
                    "Duplicate host port values are not allowed."
                )
            if public_port not in http_ports:
                public_ports_seen.add(public_port)

            # check if port is available
            if public_port not in http_ports:
                is_port_available = check_if_port_is_available_on_host(public_port)
                if not is_port_available:
                    raise serializers.ValidationError(
                        f"Port {public_port} is not available on the host machine."
                    )

        already_existing_ports = [
            str(port.host)
            for port in PortConfiguration.objects.filter(
                host__in=list(public_ports_seen)
            )
        ]

        if len(already_existing_ports) > 0:
            ports_str = ", ".join(already_existing_ports)

            if len(already_existing_ports) == 1:
                message = f"Port {ports_str} is already used by other services."
            else:
                message = f"Ports {ports_str} are already used by other services."
            raise serializers.ValidationError(message)

        return ports

    def validate_urls(self, value: list[dict[str, str]]):
        urls_seen = set()
        for url in value:
            new_url = (url["domain"], url["base_path"])
            if new_url in urls_seen:
                raise serializers.ValidationError(
                    "Duplicate urls values are not allowed."
                )
            urls_seen.add(new_url)
        return value

    def validate_volumes(self, value: list[dict[str, str]]):
        mount_paths_seen = set()
        for volume in value:
            mount_path = volume["container_path"]
            if mount_path in mount_paths_seen:
                raise serializers.ValidationError(
                    "Cannot specify the same mount_path twice or more."
                )
            mount_paths_seen.add(mount_path)
        return value


# ==============================
#       Docker deployments     #
# ==============================


class DockerServiceDeploymentFilterSet(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=DockerDeployment.DeploymentStatus.choices
    )

    class Meta:
        model = DockerDeployment
        fields = ["status", "created_at", "hash"]


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
    slug = django_filters.CharFilter(lookup_expr="istartswith")

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
    slug = django_filters.CharFilter(lookup_expr="istartswith")

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
        service: DockerRegistryService = self.context.get("service")
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
        if change_type != "DELETE" and new_value is None:
            raise serializers.ValidationError(
                {
                    "new_value": [
                        "`new_value` should be provided when the change type is `ADD` or `UPDATE`"
                    ]
                }
            )
        if change_type == "DELETE":
            attrs["new_value"] = None

        service = self.get_service()
        changes = compute_all_deployment_changes(service, attrs)
        items_with_same_id = list(
            filter(
                lambda c: c.item_id is not None and c.item_id == attrs.get("item_id"),
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
                            f"URL configuration item with id `{item_id}` does not exist."
                        ]
                    }
                )

        snapshot = compute_docker_service_snapshot_from_changes(service, attrs)
        # validate double host port
        same_urls = list(
            filter(
                lambda url: url.domain is not None
                and url.base_path is not None
                and url.domain == attrs.get("new_value", {}).get("domain")
                and url.base_path == attrs.get("new_value", {}).get("base_path"),
                snapshot.urls,
            )
        )
        if len(same_urls) >= 2:
            raise serializers.ValidationError(
                {"new_value": "Duplicate urls values for the service are not allowed."}
            )

        http_ports = [80, 443]
        if len(snapshot.urls) > 0:
            for port in snapshot.ports:
                if port.host not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "new_value": f"Cannot specify both a custom URL and a host port other than a HTTP port (80/443)"
                        }
                    )

        if (
            change_type == "DELETE"
            and snapshot.healthcheck is not None
            and snapshot.healthcheck.type == "PATH"
        ):
            ports_exposed_to_http = list(
                filter(
                    lambda port: port.host is None or port.host in [80, 443],
                    snapshot.ports,
                )
            )
            if len(snapshot.urls) == 0 and len(ports_exposed_to_http) == 0:
                raise serializers.ValidationError(
                    {
                        "new_value": f"Cannot delete an URL if there is a healthcheck attached to it"
                        f" and the service is not exposed to the public through an HTTP port (80/443)"
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
        if change_type in ["DELETE", "UPDATE"]:
            item_id = change["item_id"]

            try:
                service.volumes.get(id=item_id)
            except Volume.DoesNotExist:
                raise serializers.ValidationError(
                    {"item_id": [f"Volume with id `{item_id}` does not exist."]}
                )

        snapshot = compute_docker_service_snapshot_from_changes(service, change)

        # validate double container paths
        volumes_with_same_container_path = list(
            filter(
                lambda v: v.container_path is not None
                and v.container_path
                == change.get("new_value", {}).get("container_path"),
                snapshot.volumes,
            )
        )
        if len(volumes_with_same_container_path) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "container_path": "Cannot specify two volumes with the same `container path` for this service"
                    }
                }
            )

        # validate double host path
        volumes_with_same_host_path = list(
            filter(
                lambda v: v.host_path is not None
                and v.host_path == change.get("new_value", {}).get("host_path"),
                snapshot.volumes,
            )
        )

        if len(volumes_with_same_host_path) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host_path": "Cannot specify two volumes with the same `host path` for this service"
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
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.env_variables.get(id=item_id)
            except DockerEnvVariable.DoesNotExist:
                raise serializers.ValidationError(
                    {"item_id": [f"Env variable with id `{item_id}` does not exist."]}
                )

        # validate double `key`
        snapshot = compute_docker_service_snapshot_from_changes(service, attrs)
        envs_with_same_host_path = list(
            filter(
                lambda env: env.key is not None
                and env.key == attrs.get("new_value", {}).get("key"),
                snapshot.env_variables,
            )
        )

        if len(envs_with_same_host_path) >= 2:
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
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.ports.get(id=item_id)
            except PortConfiguration.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Port configuration item with id `{item_id}` does not exist."
                        ]
                    }
                )

        snapshot = compute_docker_service_snapshot_from_changes(service, attrs)

        # validate double host port
        ports_with_same_host = list(
            filter(
                lambda port: port.host is not None
                and port.host == attrs.get("new_value", {}).get("host"),
                snapshot.ports,
            )
        )
        if len(ports_with_same_host) >= 2:
            raise serializers.ValidationError(
                {"new_value": {"host": "Duplicate `host` port values are not allowed."}}
            )

        # validate double http port
        http_ports = [80, 443]
        ports_exposed_to_http = list(
            filter(
                lambda port: port.host is None or port.host in http_ports,
                snapshot.ports,
            )
        )
        if len(ports_exposed_to_http) >= 2:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": "Only one HTTP port (80/443) is allowed, we cannot forward the http requests to two distinct ports."
                    }
                }
            )

        # validate that url & host ports don't clash
        if len(snapshot.urls) > 0:
            for port in snapshot.ports:
                if port.host not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "new_value": {
                                "host": f"Cannot specify both a custom URL and a host port other than a HTTP port (80/443)"
                            }
                        }
                    )

        # check if port is available
        public_port = attrs.get("new_value", {}).get("host")
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
            host=public_port
        ).first()
        if already_existing_port is not None:
            raise serializers.ValidationError(
                {
                    "new_value": {
                        "host": f"host Port {already_existing_port.host} is already used by other services."
                    }
                }
            )

        return attrs


class DockerCredentialsFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["credentials"], required=True)
    new_value = DockerCredentialsRequestSerializer(required=True, allow_null=True)

    def validate(self, attrs: dict):
        service = self.get_service()
        snapshot = compute_docker_service_snapshot_from_changes(service, attrs)

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


class DockerCommandFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["command"], required=True)
    new_value = serializers.CharField(required=True, allow_null=True)


class DockerImageFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["image"], required=True)
    new_value = serializers.CharField(required=True)

    def validate(self, attrs: dict):
        service = self.get_service()
        snapshot = compute_docker_service_snapshot_from_changes(service, attrs)

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
        snapshot = compute_docker_service_snapshot_from_changes(service, attrs)

        new_healthcheck = attrs.get("new_value")
        if new_healthcheck is not None and new_healthcheck.get("type") == "PATH":
            ports_exposed_to_http = list(
                filter(
                    lambda port: port.host is None or port.host in [80, 443],
                    snapshot.ports,
                )
            )
            if len(snapshot.urls) == 0 and len(ports_exposed_to_http) == 0:
                raise serializers.ValidationError(
                    {
                        "new_value": f"healthcheck requires that at least one `url` or one `port` is provided"
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
