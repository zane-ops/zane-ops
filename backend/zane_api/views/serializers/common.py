from io import StringIO
import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from dotenv import dotenv_values
from faker import Faker

from ...dtos import DockerServiceSnapshot, DeploymentChangeDto

from ..helpers import (
    apply_changes_to_snapshot,
    build_pending_changeset_with_extra,
)
from ...serializers import (
    URLPathField,
    URLDomainField,
    CustomChoiceField,
    ServiceSerializer,
)
from rest_framework import serializers

from ...models import (
    URL,
    Service,
    DeploymentURL,
    DeploymentChange,
)
from temporal.helpers import get_server_resource_limits
from ...utils import (
    convert_value_to_bytes,
    format_storage_value,
)
from ...validators import validate_url_path, validate_env_name


# ==============================
#        Service fields        #
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
    mount_path = URLPathField(required=True)
    language = serializers.CharField(default="plaintext", required=False)

    def validate(self, attrs: dict):
        if attrs.get("name") is None:
            fake = Faker()
            Faker.seed(time.monotonic())
            attrs["name"] = fake.slug().lower()
        return attrs


class VolumeRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, min_length=1)
    container_path = URLPathField(max_length=255)
    host_path = URLPathField(max_length=255, required=False, default=None)
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
                            "Volumes with a host path can only be mounted in `read only` mode."
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
    domain = URLDomainField(required=False)
    base_path = URLPathField(required=False, default="/")
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
                        "To expose this service, you need to add an associated port to forward this URL to."
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
                        "You cannot provide an associated port if this URL is redirect URL."
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
    type = CustomChoiceField(required=True, choices=HEALTHCHECK_CHOICES)
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
        snapshot = apply_changes_to_snapshot(
            DockerServiceSnapshot.from_dict(
                ServiceSerializer(service).data  # type: ignore
            ),
            [*env_changes, *build_pending_changeset_with_extra(service)],
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
