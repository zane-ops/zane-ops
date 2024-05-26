import django_filters
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter
from rest_framework import pagination

from .. import serializers
from ..docker_operations import (
    check_if_docker_image_exists,
)
from ..models import (
    URL,
    DockerDeployment,
    Project,
    ArchivedProject,
    DockerRegistryService,
    DockerDeploymentChange,
    Volume,
    DockerEnvVariable,
    PortConfiguration,
)
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
    # command = serializers.CharField(required=False)
    # urls = URLRequestSerializer(many=True, required=False, default=[])
    # ports = ServicePortsRequestSerializer(required=False, many=True, default=[])
    # env = serializers.DictField(child=serializers.CharField(), required=False)
    # volumes = VolumeRequestSerializer(many=True, required=False, default=[])
    # healthcheck = HealthCheckRequestSerializer(required=False)

    def validate(self, data: dict):
        credentials = data.get("credentials")
        image = data.get("image")
        # healthcheck = data.get("healthcheck")

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=dict(credentials) if credentials is not None else None,
        )
        if not do_image_exists:
            raise serializers.ValidationError(
                {
                    "image": [
                        f"Either the image `{image}` does not exist in the specified registry"
                        f" or the credentials are invalid for this image."
                        f" Have you forgotten to include the credentials ?"
                    ]
                }
            )

        # urls = data.get("urls", [])
        # ports = data.get("ports", [])
        #
        # http_ports = [80, 443]
        # if len(urls) > 0:
        #     for port in ports:
        #         if port["public"] not in http_ports:
        #             raise serializers.ValidationError(
        #                 {
        #                     "urls": [
        #                         f"Cannot specify both a custom URL and a public port other than a HTTP port (80/443)"
        #                     ]
        #                 }
        #             )
        #
        # if healthcheck is not None and healthcheck["type"].lower() == "path":
        #     if len(ports) == 0 and len(urls) == 0:
        #         raise serializers.ValidationError(
        #             {
        #                 "healthcheck": {
        #                     "path": [
        #                         f"healthcheck requires that at least one `url` or one `port` is provided"
        #                     ]
        #                 }
        #             }
        #         )
        return data

    # def validate_ports(self, ports: list[dict[str, int]]):
    #     no_of_http_ports = 0
    #     http_ports = [80, 443]
    #     public_ports_seen = set()
    #     for port in ports:
    #         public_port = port["public"]
    #
    #         # Check for only 1 http port
    #         if public_port in http_ports:
    #             no_of_http_ports += 1
    #         if no_of_http_ports > 1:
    #             raise serializers.ValidationError("Only one HTTP port is allowed")
    #
    #         # Check for duplicate public ports
    #         if public_port in public_ports_seen:
    #             raise serializers.ValidationError(
    #                 "Duplicate public port values are not allowed."
    #             )
    #         if public_port not in http_ports:
    #             public_ports_seen.add(public_port)
    #
    #         # check if port is available
    #         if public_port not in http_ports:
    #             is_port_available = check_if_port_is_available_on_host(public_port)
    #             if not is_port_available:
    #                 raise serializers.ValidationError(
    #                     f"Port {public_port} is not available on the host machine."
    #                 )
    #
    #     already_existing_ports = [
    #         str(port.host)
    #         for port in PortConfiguration.objects.filter(
    #             host__in=list(public_ports_seen)
    #         )
    #     ]
    #
    #     if len(already_existing_ports) > 0:
    #         ports_str = ", ".join(already_existing_ports)
    #
    #         if len(already_existing_ports) == 1:
    #             message = f"Port {ports_str} is already used by other services."
    #         else:
    #             message = f"Ports {ports_str} are already used by other services."
    #         raise serializers.ValidationError(message)
    #
    #     return ports
    #
    # def validate_urls(self, value: list[dict[str, str]]):
    #     urls_seen = set()
    #     for url in value:
    #         new_url = (url["domain"], url["base_path"])
    #         if new_url in urls_seen:
    #             raise serializers.ValidationError(
    #                 "Duplicate urls values are not allowed."
    #             )
    #         urls_seen.add(new_url)
    #     return value
    #
    # def validate_volumes(self, value: list[dict[str, str]]):
    #     mount_paths_seen = set()
    #     for volume in value:
    #         mount_path = volume["mount_path"]
    #         if mount_path in mount_paths_seen:
    #             raise serializers.ValidationError(
    #                 "Cannot specify the same mount_path twice or more."
    #             )
    #         mount_paths_seen.add(mount_path)
    #     return value
    #


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
#      Projects Statuses       #
# ==============================


class ProjectStatusSerializer(serializers.Serializer):
    healthy_services = serializers.IntegerField(min_value=0)
    total_services = serializers.IntegerField(min_value=0)


class ProjectStatusResponseSerializer(serializers.Serializer):
    projects = serializers.DictField(child=ProjectStatusSerializer())


class ProjectStatusRequestParamsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField(), required=True)


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


class DockerServiceUpdateResponseSerializer(serializers.Serializer):
    pass


# ==============================
#    Docker services changes   #
# ==============================


class BaseChangeItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["ADD", "DELETE", "UPDATE"], required=True)
    item_id = serializers.CharField(max_length=255, required=False)
    new_value = serializers.SerializerMethodField()

    def get_service(self):
        service: DockerRegistryService = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")
        return service

    def get_new_value(self, obj):
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
        return attrs


class BaseListChangeSerializer(serializers.ListSerializer):
    child = BaseChangeItemSerializer()

    def get_service(self):
        service: DockerRegistryService = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")
        return service

    @property
    def current_field(self) -> str:
        raise NotImplementedError("This should be implemented in child classes.")

    def validate(self, attrs: list[dict]):
        service = self.get_service()
        existing_changes = service.unapplied_changes.filter(
            field=self.current_field, type__in=["UPDATE", "DELETE"]
        ).all()

        id_set = set(
            map(
                lambda field_change: field_change.item_id,
                existing_changes,
            )
        )
        for change in attrs:
            if change["type"] in ["UPDATE", "DELETE"]:
                item_id = change["item_id"]

                if item_id in id_set:
                    raise serializers.ValidationError(
                        "Cannot make conflicting changes for this field"
                    )
                id_set.add(item_id)
        return attrs


class BaseChangeFieldSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["UPDATE"], required=False, default="UPDATE")
    new_value = serializers.SerializerMethodField()

    def get_new_value(self, obj):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )


class URLItemChangeSerializer(BaseChangeItemSerializer):
    new_value = URLRequestSerializer(required=True, allow_null=True)

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
        return attrs


class URLListChangeSerialiazer(BaseListChangeSerializer):
    child = URLItemChangeSerializer()

    @property
    def current_field(self) -> str:
        return "urls"


class VolumeItemChangeSerializer(BaseChangeItemSerializer):
    new_value = VolumeRequestSerializer(required=False)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                service.volumes.get(id=item_id)
            except Volume.DoesNotExist:
                raise serializers.ValidationError(
                    {"item_id": [f"Volume with id `{item_id}` does not exist."]}
                )
        return attrs


class VolumeListChangeSerialiazer(BaseListChangeSerializer):
    child = VolumeItemChangeSerializer()

    @property
    def current_field(self) -> str:
        return "volumes"


class EnvItemChangeSerializer(BaseChangeItemSerializer):
    new_value = EnvRequestSerializer()

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
        return attrs


class EnvListChangeSerialiazer(BaseListChangeSerializer):
    child = EnvItemChangeSerializer()

    @property
    def current_field(self) -> str:
        return "env_variables"


class PortItemChangeSerializer(BaseChangeItemSerializer):
    new_value = ServicePortsRequestSerializer(required=True, allow_null=True)

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
        return attrs


class PortListChangeSerialiazer(BaseListChangeSerializer):
    child = PortItemChangeSerializer()

    @property
    def current_field(self) -> str:
        return "ports"


class DockerCredentialsChangeFieldSerializer(BaseChangeFieldSerializer):
    new_value = DockerCredentialsRequestSerializer(required=True, allow_null=True)


class DockerCommandChangeFieldSerializer(BaseChangeFieldSerializer):
    new_value = serializers.CharField(required=True, allow_null=True)


class DockerImageChangeFieldSerializer(BaseChangeFieldSerializer):
    new_value = serializers.CharField(required=True)


class HealthcheckChangeFieldSerializer(BaseChangeFieldSerializer):
    new_value = HealthCheckRequestSerializer(required=True, allow_null=True)


class DockerServiceChangesRequestSerializer(serializers.Serializer):
    image = DockerImageChangeFieldSerializer(required=False)
    credentials = DockerCredentialsChangeFieldSerializer(required=False)
    command = DockerCommandChangeFieldSerializer(required=False)
    healthcheck = HealthcheckChangeFieldSerializer(required=False)
    volumes = VolumeListChangeSerialiazer(required=False)
    urls = URLListChangeSerialiazer(required=False)
    ports = PortListChangeSerialiazer(required=False)
    env_variables = EnvListChangeSerialiazer(required=False)

    def get_service(self):
        service: DockerRegistryService = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")
        return service

    def validate(self, attrs: dict[str, dict | list[dict]]):
        if not bool(attrs):
            raise serializers.ValidationError("please provide at least one change")

        credential_changes = attrs.get("credentials")
        if credential_changes is not None:
            self._validate_credentials(credential_changes, attrs)

        return attrs

    def validate_volumes(self, changes: list[dict]):
        if changes is None or len(changes) == 0:
            return changes

        mount_path_set = set()
        service = self.get_service()
        volume_changes: list[DockerDeploymentChange] = list(
            service.unapplied_changes.filter(field="volumes").all()
        )
        volumes = service.volumes.all()

        # Validate double `container_path`
        existing_mount_path_set = set(
            map(
                lambda v_change: (
                    v_change.new_value.get("container_path")
                    if v_change.new_value is not None
                    else None
                ),
                volume_changes,
            )
        )

        existing_mount_path_set.update(
            map(
                lambda volume: volume.container_path,
                volumes,
            )
        )

        for change in changes:
            current_mount_path = change["new_value"]["container_path"]

            if (
                current_mount_path in mount_path_set
                or current_mount_path in existing_mount_path_set
            ):
                raise serializers.ValidationError(
                    "Cannot specify two volumes with the same container path for this service"
                )

            mount_path_set.add(current_mount_path)
        return changes

    def _validate_credentials(self, change: dict, attrs: dict[str, dict | list[dict]]):
        credentials = change.get("new_value")
        if credentials is None:
            return credentials

        service = self.get_service()
        image = service.image or attrs.get("image", {}).get("new_value")

        if image is None:
            image_change: DockerDeploymentChange = service.unapplied_changes.filter(
                field="image"
            ).first()

            image = image_change.new_value if image_change is not None else None

            if image is None:
                raise serializers.ValidationError(
                    {
                        "credentials": [
                            "Cannot provide `credentials` without a provided image for the service."
                        ]
                    }
                )

        do_image_exists = check_if_docker_image_exists(
            image,
            credentials=dict(credentials),
        )
        if not do_image_exists:
            raise serializers.ValidationError(
                {
                    "credentials": [
                        f"The credentials are invalid for the image `{image}` provided for the service."
                    ]
                }
            )

        return change

    # def validate_ports(self, changes: list[dict[str, dict[str, int]]]):
    #     new_ports = map(
    #         lambda change: change["new_value"],
    #         filter(lambda change: change["type"] == "add", changes),
    #     )
    #
    #     no_of_http_ports = 0
    #     http_ports = [80, 443]
    #     public_ports_seen = set()
    #     for port in new_ports:
    #         public_port = port["public"]
    #
    #         # Check for only 1 http port
    #         if public_port in http_ports:
    #             no_of_http_ports += 1
    #         if no_of_http_ports > 1:
    #             raise serializers.ValidationError("Only one HTTP port is allowed")
    #
    #         # Check for duplicate public ports
    #         if public_port in public_ports_seen:
    #             raise serializers.ValidationError(
    #                 "Duplicate public port values are not allowed."
    #             )
    #         if public_port not in http_ports:
    #             public_ports_seen.add(public_port)
    #
    #         # check if port is available
    #         if public_port not in http_ports:
    #             is_port_available = check_if_port_is_available_on_host(public_port)
    #             if not is_port_available:
    #                 raise serializers.ValidationError(
    #                     f"Port {public_port} is not available on the host machine."
    #                 )
    #
    #     already_existing_ports = [
    #         str(port.host)
    #         for port in PortConfiguration.objects.filter(
    #             host__in=list(public_ports_seen)
    #         )
    #     ]
    #
    #     if len(already_existing_ports) > 0:
    #         ports_str = ", ".join(already_existing_ports)
    #
    #         if len(already_existing_ports) == 1:
    #             message = f"Port {ports_str} is already used by other services."
    #         else:
    #             message = f"Ports {ports_str} are already used by other services."
    #         raise serializers.ValidationError(message)
    #
    #     return changes
