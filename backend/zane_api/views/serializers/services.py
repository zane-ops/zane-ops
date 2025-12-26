import json
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ..helpers import (
    compute_snapshot_including_change,
    build_pending_changeset_with_extra,
)
from rest_framework import serializers
from ...models import (
    URL,
    Service,
    Volume,
    EnvVariable,
    PortConfiguration,
    Config,
    GitApp,
    DeploymentChange,
    SharedVolume,
)
from temporal.helpers import (
    check_if_docker_image_exists,
    check_if_port_is_available_on_host,
)
from ...utils import EnhancedJSONEncoder, find_item_in_sequence, add_suffix_if_missing
from ...git_client import GitClient
from ...validators import validate_git_commit_sha
from ...constants import HEAD_COMMIT
from .common import (
    ConfigRequestSerializer,
    EnvRequestSerializer,
    HealthCheckRequestSerializer,
    ResourceLimitsRequestSerializer,
    ServicePortsRequestSerializer,
    SharedVolumeRequestSerializer,
    URLRequestSerializer,
    VolumeRequestSerializer,
)

from git_connectors.models import GitRepository
from container_registry.models import SharedRegistryCredentials

# ==============================
#    Docker services create    #
# ==============================


class DockerServiceCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=38, required=False)
    image = serializers.CharField(required=True)
    container_registry_credentials_id = serializers.CharField(required=False)

    def validate_container_registry_credentials_id(self, value: str):
        if not SharedRegistryCredentials.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f"A container registry with an ID of `{value}` does not exist."
            )
        return value

    def validate(self, attrs: dict):
        registry_credentials_id = attrs.get("container_registry_credentials_id")
        credentials: dict | None = None

        if registry_credentials_id is not None:
            registry_credentials = SharedRegistryCredentials.objects.get(
                pk=registry_credentials_id
            )

            if registry_credentials.password is not None:
                credentials = dict(
                    username=registry_credentials.username,
                    password=registry_credentials.password,
                )

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
    slug = serializers.SlugField(max_length=38, required=False)
    repository_url = serializers.URLField(required=True)
    branch_name = serializers.CharField(required=True)
    git_app_id = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, str]):
        repository_url = add_suffix_if_missing(
            attrs["repository_url"].rstrip("/"), ".git"
        )
        branch_name = attrs["branch_name"]

        computed_repository_url = repository_url

        client = GitClient()

        if attrs.get("git_app_id") is not None:
            try:
                gitapp = (
                    GitApp.objects.filter(
                        Q(id=attrs.get("git_app_id"))
                        & (Q(github__isnull=False) | Q(gitlab__isnull=False))
                    )
                    .select_related("github", "gitlab")
                    .get()
                )
            except GitApp.DoesNotExist:
                raise serializers.ValidationError("This git app does not exists")

            if gitapp.github is not None:
                github = gitapp.github
                if not github.is_installed:
                    raise serializers.ValidationError(
                        "This GitHub app needs to be installed before it can be used"
                    )

                try:
                    github.repositories.get(url=repository_url)
                except GitRepository.DoesNotExist:
                    raise serializers.ValidationError(
                        {
                            "repository_url": [
                                f"The selected github app does not have access to the repository `{repository_url}`."
                            ]
                        }
                    )
                computed_repository_url = github.get_authenticated_repository_url(
                    repository_url
                )

            if gitapp.gitlab is not None:
                gitlab = gitapp.gitlab
                if not gitlab.is_installed:
                    raise serializers.ValidationError(
                        "This Gitlab app needs to be installed before it can be used"
                    )

                try:
                    gitlab.repositories.get(url=repository_url)
                except GitRepository.DoesNotExist:
                    raise serializers.ValidationError(
                        {
                            "repository_url": [
                                f"The selected gitlab app does not have access to the repository `{repository_url}`."
                            ]
                        }
                    )
                computed_repository_url = gitlab.get_authenticated_repository_url(
                    repository_url
                )

        is_valid_repository = client.check_if_git_repository_is_valid(
            computed_repository_url, branch_name
        )
        if not is_valid_repository:
            raise serializers.ValidationError(
                {
                    "repository_url": [
                        "The specified repository or branch may not or does not exist, or the repository could be private."
                    ]
                }
            )

        return {**attrs, "repository_url": repository_url}


class GitServiceDockerfileBuilderRequestSerializer(GitServiceCreateRequestSerializer):
    dockerfile_path = serializers.CharField(default="./Dockerfile")
    build_context_dir = serializers.CharField(default="./")
    builder = serializers.ChoiceField(
        choices=[Service.Builder.DOCKERFILE], default=Service.Builder.DOCKERFILE
    )


class GitServiceStaticDirBuilderRequestSerializer(GitServiceCreateRequestSerializer):
    publish_directory = serializers.CharField(default="./")
    is_spa = serializers.BooleanField(default=False)
    not_found_page = serializers.CharField(required=False, allow_null=True)
    index_page = serializers.CharField(default="./index.html")
    builder = serializers.ChoiceField(
        choices=[Service.Builder.STATIC_DIR], default=Service.Builder.STATIC_DIR
    )


class GitServiceNixpacksBuilderRequestSerializer(GitServiceCreateRequestSerializer):
    build_directory = serializers.CharField(default="./")
    is_static = serializers.BooleanField(default=False)
    is_spa = serializers.BooleanField(default=False)
    publish_directory = serializers.CharField(default="./dist")
    exposed_port = serializers.IntegerField(min_value=1, default=80)
    builder = serializers.ChoiceField(
        choices=[Service.Builder.NIXPACKS], default=Service.Builder.NIXPACKS
    )


class GitServiceRailpackBuilderRequestSerializer(GitServiceCreateRequestSerializer):
    build_directory = serializers.CharField(default="./")
    is_static = serializers.BooleanField(default=False)
    is_spa = serializers.BooleanField(default=False)
    publish_directory = serializers.CharField(default="./dist")
    exposed_port = serializers.IntegerField(min_value=1, default=80)
    builder = serializers.ChoiceField(
        choices=[Service.Builder.RAILPACK], default=Service.Builder.RAILPACK
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
    cleanup_queue = serializers.BooleanField(default=False)


# ==============================
#      Git service deploy      #
# ==============================


class GitServiceDeployRequestSerializer(serializers.Serializer):
    ignore_build_cache = serializers.BooleanField(default=False)
    cleanup_queue = serializers.BooleanField(default=False)


# =================================
#       Git service redeploy      #
# =================================


class GitServiceReDeployRequestSerializer(serializers.Serializer):
    ignore_build_cache = serializers.BooleanField(default=True)


# ====================================
#    Docker service webhook deploy   #
# ====================================


class DockerServiceWebhookDeployRequestSerializer(serializers.Serializer):
    commit_message = serializers.CharField(required=False, allow_blank=True)
    new_image = serializers.CharField(required=False)
    cleanup_queue = serializers.BooleanField(required=False)

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


# ====================================
#     Git service webhook deploy     #
# ====================================


class GitServiceWebhookDeployRequestSerializer(serializers.Serializer):
    ignore_build_cache = serializers.BooleanField(default=False)
    commit_sha = serializers.CharField(
        default=HEAD_COMMIT, validators=[validate_git_commit_sha]
    )
    cleanup_queue = serializers.BooleanField(required=False)


# ==============================
#       service Update         #
# ==============================


class ServiceUpdateRequestSerializer(serializers.Serializer):
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
            changes = build_pending_changeset_with_extra(service, attrs)
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

        snapshot = compute_snapshot_including_change(service, attrs)
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

            # For DELETE, check if volume is referenced in any shared volumes
            if change_type == "DELETE":
                # Check if volume is currently being shared by other services
                if SharedVolume.objects.filter(volume=current_volume).exists():
                    raise serializers.ValidationError(
                        {
                            "item_id": [
                                "Cannot delete volume that is currently shared with other services."
                            ]
                        }
                    )

                # Check if volume is referenced in pending shared volume changes
                pending_shared_volume_changes = DeploymentChange.objects.filter(
                    field=DeploymentChange.ChangeField.SHARED_VOLUMES,
                    new_value__volume_id=current_volume.id,
                    applied=False,
                ).exclude(service=service)

                if pending_shared_volume_changes.exists():
                    raise serializers.ValidationError(
                        {
                            "item_id": [
                                "Cannot delete volume that is referenced in shared volumes by another service."
                            ]
                        }
                    )

        snapshot = compute_snapshot_including_change(service, attrs)

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
                            "host_path": "Cannot remove the host path from a volume that was originally mounted with one, "
                            "you need to delete and recreate the volume without the host path."
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
                            "host_path": "Cannot mount a volume to a host path if it wasn't originally mounted that way, "
                            "you need to delete and recreate the volume with a host path."
                        }
                    }
                )

        return attrs


class SharedVolumeItemChangeSerializer(BaseChangeItemSerializer):
    new_value = SharedVolumeRequestSerializer(required=False)
    field = serializers.ChoiceField(choices=["shared_volumes"], required=True)

    def validate(self, attrs: dict):
        super().validate(attrs)
        service = self.get_service()
        change_type = attrs["type"]
        new_value = attrs.get("new_value") or {}

        # Validate DELETE and UPDATE operations
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]
            try:
                current_shared_volume = service.shared_volumes.get(id=item_id)
            except SharedVolume.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Shared volume with id `{item_id}` does not exist for this service."
                        ]
                    }
                )

        # Validate no duplicate container paths (including owned volumes and shared volumes)
        if change_type in ["ADD", "UPDATE"]:
            container_path = new_value.get("container_path")

            # Check against owned volumes
            if service.volumes.filter(container_path=container_path).exists():
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "container_path": f"Container path `{container_path}` is already used by an owned volume."
                        }
                    }
                )

            # Check against other shared volumes
            existing_shared = service.shared_volumes.filter(
                container_path=container_path
            )
            if change_type == "UPDATE":
                existing_shared = existing_shared.exclude(id=attrs.get("item_id"))

            if existing_shared.exists():
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "container_path": f"Container path `{container_path}` is already used by another shared volume."
                        }
                    }
                )

        # For ADD operations, validate the volume is shareable
        if change_type == "ADD":
            volume_id = new_value.get("volume_id")

            # Check if already sharing this volume
            if SharedVolume.objects.filter(
                reader=service, volume__id=volume_id
            ).exists():
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "volume_id": "This service is already sharing this volume."
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
        snapshot = compute_snapshot_including_change(service, attrs)

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

        volume_with_same_container_path = find_item_in_sequence(
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
        snapshot = compute_snapshot_including_change(service, attrs)
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

        snapshot = compute_snapshot_including_change(service, attrs)

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
    container_registry_credentials_id = serializers.CharField(required=False)

    def validate_container_registry_credentials_id(self, value: str):
        if not SharedRegistryCredentials.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f"A container registry with an ID of `{value}` does not exist."
            )
        return value

    def validate(self, attrs: dict):
        registry_credentials_id = attrs.get("container_registry_credentials_id")
        credentials: dict | None = None

        if registry_credentials_id is not None:
            registry_credentials = SharedRegistryCredentials.objects.get(
                pk=registry_credentials_id
            )

            if registry_credentials.password is not None:
                credentials = dict(
                    username=registry_credentials.username,
                    password=registry_credentials.password,
                )

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


class DockerSourceFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["source"], required=True)
    new_value = DockerSourceRequestSerializer(required=True)


class GitSourceRequestSerializer(serializers.Serializer):
    repository_url = serializers.URLField(required=True)
    branch_name = serializers.CharField(required=True)
    commit_sha = serializers.CharField(
        default=HEAD_COMMIT, validators=[validate_git_commit_sha]
    )
    git_app_id = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, str]):
        repository_url = add_suffix_if_missing(
            attrs["repository_url"].rstrip("/"), ".git"
        )
        branch_name = attrs["branch_name"]
        git = GitClient()

        computed_repository_url = repository_url

        if attrs.get("git_app_id") is not None:
            try:
                gitapp = (
                    GitApp.objects.filter(
                        Q(id=attrs.get("git_app_id"))
                        & (Q(github__isnull=False) | Q(gitlab__isnull=False))
                    )
                    .select_related("github", "gitlab")
                    .get()
                )
            except GitApp.DoesNotExist:
                raise serializers.ValidationError("This git app does not exists")

            if gitapp.github is not None:
                github = gitapp.github
                if not github.is_installed:
                    raise serializers.ValidationError(
                        "This GitHub app needs to be installed before it can be used"
                    )

                try:
                    github.repositories.get(url=repository_url)
                except GitRepository.DoesNotExist:
                    raise serializers.ValidationError(
                        {
                            "repository_url": [
                                f"The selected github app does not have access to the repository `{repository_url}`."
                            ]
                        }
                    )
                computed_repository_url = github.get_authenticated_repository_url(
                    repository_url
                )

            elif gitapp.gitlab is not None:
                gitlab = gitapp.gitlab
                if not gitlab.is_installed:
                    raise serializers.ValidationError(
                        "This Gitlab app needs to be installed before it can be used"
                    )

                try:
                    gitlab.repositories.get(url=repository_url)
                except GitRepository.DoesNotExist:
                    raise serializers.ValidationError(
                        {
                            "repository_url": [
                                f"The selected gitlab app does not have access to the repository `{repository_url}`."
                            ]
                        }
                    )
                computed_repository_url = gitlab.get_authenticated_repository_url(
                    repository_url
                )

        is_valid_repository = git.check_if_git_repository_is_valid(
            computed_repository_url, branch_name
        )
        if not is_valid_repository:
            raise serializers.ValidationError(
                {
                    "repository_url": [
                        "The specified repository or branch may not or does not exist, or the repository could be private."
                    ]
                }
            )

        return {
            **attrs,
            "repository_url": repository_url,
        }


class GitSourceFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["git_source"], required=True)
    new_value = GitSourceRequestSerializer(required=True)


class BuilderRequestSerializer(serializers.Serializer):
    builder = serializers.ChoiceField(
        choices=Service.Builder.choices, default=Service.Builder.DOCKERFILE
    )

    # Dockerfile builder
    build_context_dir = serializers.CharField(default="./")
    dockerfile_path = serializers.CharField(default="./Dockerfile")
    build_stage_target = serializers.CharField(required=False, allow_null=True)

    # Static directory builder
    publish_directory = serializers.CharField(default="./")
    is_spa = serializers.BooleanField(default=False)
    not_found_page = serializers.CharField(required=False, allow_null=True)
    index_page = serializers.CharField(default="./index.html")

    # Nixpacks builder
    is_static = serializers.BooleanField(default=False)
    build_directory = serializers.CharField(default="./")
    custom_install_command = serializers.CharField(allow_null=True, required=False)
    custom_build_command = serializers.CharField(allow_null=True, required=False)
    custom_start_command = serializers.CharField(allow_null=True, required=False)


class GitBuilderFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["builder"], required=True)
    new_value = BuilderRequestSerializer(required=True)


class DockerCommandFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["command"], required=True)
    new_value = serializers.CharField(required=True, allow_null=True)


class HealthcheckFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(choices=["healthcheck"], required=True)
    new_value = HealthCheckRequestSerializer(required=True, allow_null=True)


class DockerDeploymentFieldChangeRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        required=True,
        choices=DeploymentChange.ChangeField.choices,
    )


# ==========================================
#         Toggle Service state             #
# ==========================================


class ToggleServiceStateRequestSerializer(serializers.Serializer):
    desired_state = serializers.ChoiceField(choices=["start", "stop"])


class BulkToggleServiceStateRequestSerializer(serializers.Serializer):
    desired_state = serializers.ChoiceField(choices=["start", "stop"])
    service_ids = serializers.ListField(child=serializers.CharField())


# ==========================================
#         Bulk deploy services             #
# ==========================================


class BulkDeployServiceRequestSerializer(serializers.Serializer):
    service_ids = serializers.ListField(child=serializers.CharField())
