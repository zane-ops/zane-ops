import django_filters
import docker.errors
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter
from rest_framework import pagination

from .. import serializers
from ..docker_operations import (
    DOCKER_HUB_REGISTRY_URL,
    login_to_docker_registry,
    check_if_docker_image_exists,
    check_if_port_is_available_on_host,
)
from ..models import URL, PortConfiguration, DockerDeployment, Project, ArchivedProject
from ..validators import validate_url_path


# ==============================
#    Docker services create    #
# ==============================


class DockerCredentialsRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)
    registry_url = serializers.URLField(required=False, default=DOCKER_HUB_REGISTRY_URL)


class ServicePortsRequestSerializer(serializers.Serializer):
    public = serializers.IntegerField(required=False, default=80)
    forwarded = serializers.IntegerField(required=True)


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    mount_path = serializers.CharField(max_length=255)
    host_path = serializers.URLPathField(max_length=255, required=False)
    VOLUME_MODE_CHOICES = (
        ("ro", _("READ_ONLY")),
        ("rw", _("READ_WRITE")),
    )
    mode = serializers.ChoiceField(
        required=False, choices=VOLUME_MODE_CHOICES, default="rw"
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
                        f"URL with domain `{url['domain']}` can't be used because it will be shadowed by the wildcard"
                        f" domain `{domain_as_wildcard}` which is already assigned to another service."
                    ]
                }
            )

        return url


class HealthCheckRequestSerializer(serializers.Serializer):
    HEALTCHECK_CHOICES = (
        ("path", _("path")),
        ("command", _("command")),
    )
    type = serializers.CaseInsensitiveChoiceField(
        required=True, choices=HEALTCHECK_CHOICES
    )
    value = serializers.CharField(max_length=255, required=True)
    timeout_seconds = serializers.IntegerField(required=False, default=60, min_value=5)
    interval_seconds = serializers.CharField(required=False, default=30)

    def validate(self, data: dict):
        if data["type"] == "path":
            try:
                validate_url_path(data["value"])
            except ValidationError as e:
                raise serializers.ValidationError({"value": e.messages})
        return data


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)
    image = serializers.CharField(required=True)
    command = serializers.CharField(required=False)
    credentials = DockerCredentialsRequestSerializer(required=False)
    urls = URLRequestSerializer(many=True, required=False, default=[])
    ports = ServicePortsRequestSerializer(required=False, many=True, default=[])
    env = serializers.DictField(child=serializers.CharField(), required=False)
    volumes = VolumeRequestSerializer(many=True, required=False, default=[])
    healthcheck = HealthCheckRequestSerializer(required=False)

    def validate(self, data: dict):
        credentials = data.get("credentials")
        image = data.get("image")
        healthcheck = data.get("healthcheck")

        if credentials is not None:
            try:
                login_to_docker_registry(**dict(credentials))
            except docker.errors.APIError:
                raise serializers.ValidationError(
                    {"credentials": [f"Invalid credentials for the specified registry"]}
                )

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=dict(credentials) if credentials is not None else None,
        )
        if not do_image_exists:
            registry_url = (
                credentials.get("registry_url") if credentials is not None else None
            )
            if registry_url == DOCKER_HUB_REGISTRY_URL or registry_url is None:
                registry_str = "on Docker Hub"
            else:
                registry_str = f"in the specified registry"
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` does not exist `{registry_str}`"
                        f" or the credentials are invalid for this image."
                        f" Have you forgotten to include the credentials ?"
                    ]
                }
            )

        urls = data.get("urls", [])
        ports = data.get("ports", [])

        http_ports = [80, 443]
        if len(urls) > 0:
            for port in ports:
                if port["public"] not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "urls": [
                                f"Cannot specify both a custom URL and a public port other than a HTTP port (80/443)"
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

    def validate_credentials(self, value: dict):
        try:
            login_to_docker_registry(
                username=value["username"],
                password=value["password"],
                registry_url=value.get("registry_url"),
            )
        except docker.errors.APIError:
            raise serializers.ValidationError("Invalid docker credentials")
        else:
            return value

    def validate_ports(self, ports: list[dict[str, int]]):
        no_of_http_ports = 0
        http_ports = [80, 443]
        public_ports_seen = set()
        for port in ports:
            public_port = port["public"]

            # Check for only 1 http port
            if public_port in http_ports:
                no_of_http_ports += 1
            if no_of_http_ports > 1:
                raise serializers.ValidationError("Only one HTTP port is allowed")

            # Check for duplicate public ports
            if public_port in public_ports_seen:
                raise serializers.ValidationError(
                    "Duplicate public port values are not allowed."
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
            mount_path = volume["mount_path"]
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
#    Docker services update    #
# ==============================


class DockerServiceUpdateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=True)


# ==============================
#    Docker services deploy    #
# ==============================


class DockerServiceDeployRequestSerializer(serializers.Serializer):
    image_tag = serializers.CharField(required=False)
    command = serializers.CharField(required=False)
    credentials = DockerCredentialsRequestSerializer(required=False)
    urls = URLRequestSerializer(many=True, required=False)
    ports = ServicePortsRequestSerializer(required=False, many=True)
    env = serializers.DictField(child=serializers.CharField(), required=False)
    volumes = VolumeRequestSerializer(many=True, required=False)
    healthcheck = HealthCheckRequestSerializer(required=False)

    def __init__(self, image_repository: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_repository = image_repository

    def validate(self, data: dict):
        credentials = data.get("credentials")
        healthcheck = data.get("healthcheck")
        image_tag = data.get("image_tag")

        if credentials is not None:
            try:
                login_to_docker_registry(**dict(credentials))
            except docker.errors.APIError:
                raise serializers.ValidationError(
                    {"credentials": [f"Invalid credentials for the specified registry"]}
                )

        if image_tag is not None:
            image = f"{self.image_repository}:{self.image_tag}"
            do_image_exists = check_if_docker_image_exists(
                image,
                credentials=dict(credentials) if credentials is not None else None,
            )
            if not do_image_exists:
                registry_url = (
                    credentials.get("registry_url") if credentials is not None else None
                )
                if registry_url == DOCKER_HUB_REGISTRY_URL or registry_url is None:
                    registry_str = "on Docker Hub"
                else:
                    registry_str = f"in the specified registry"
                raise serializers.ValidationError(
                    {
                        "image": [
                            f"Either the image `{image}` does not exist `{registry_str}`"
                            f" or the credentials are invalid for this image."
                            f" Have you forgotten to include the credentials ?"
                        ]
                    }
                )

        urls = data.get("urls", [])
        ports = data.get("ports", [])

        http_ports = [80, 443]
        if len(urls) > 0:
            for port in ports:
                if port["public"] not in http_ports:
                    raise serializers.ValidationError(
                        {
                            "urls": [
                                f"Cannot specify both a custom URL and a public port other than a HTTP port (80/443)"
                            ]
                        }
                    )

        if healthcheck is not None and healthcheck["type"].lower() == "path":
            if len(ports) == 0 and len(urls) == 0:
                raise serializers.ValidationError(
                    {
                        "healthcheck": {
                            "path": [
                                f"path healthcheck requires that at least one `url` or one `port` is provided"
                            ]
                        }
                    }
                )
        return data

    def validate_credentials(self, value: dict):
        try:
            login_to_docker_registry(
                username=value["username"],
                password=value["password"],
                registry_url=value.get("registry_url"),
            )
        except docker.errors.APIError:
            raise serializers.ValidationError("Invalid docker credentials")
        else:
            return value

    def validate_ports(self, ports: list[dict[str, int]]):
        no_of_http_ports = 0
        http_ports = [80, 443]
        public_ports_seen = set()
        for port in ports:
            public_port = port["public"]

            # Check for only 1 http port
            if public_port in http_ports:
                no_of_http_ports += 1
            if no_of_http_ports > 1:
                raise serializers.ValidationError("Only one HTTP port is allowed")

            # Check for duplicate public ports
            if public_port in public_ports_seen:
                raise serializers.ValidationError(
                    "Duplicate public port values are not allowed."
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
            mount_path = volume["mount_path"]
            if mount_path in mount_paths_seen:
                raise serializers.ValidationError(
                    "Cannot specify the same mount_path twice or more."
                )
            mount_paths_seen.add(mount_path)
        return value
