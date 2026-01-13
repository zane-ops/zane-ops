import base64
import json
import subprocess
import tempfile
import tomllib
from typing import Any, cast
from rest_framework import serializers
import yaml
from ..models import (
    ComposeStack,
    ComposeStackChange,
    ComposeStackEnvOverride,
    ComposeStackDeployment,
)
from faker import Faker
import time
from ..processor import ComposeSpecProcessor
from zane_api.models import Project, Environment
from django.core.exceptions import ValidationError
from ..dtos import ComposeStackServiceStatus
from zane_api.utils import DockerSwarmTaskState, EnhancedJSONEncoder
from django.db import transaction
from zane_api.views.serializers import EnvRequestSerializer
from django.utils.translation import gettext_lazy as _
from drf_standardized_errors.formatter import ExceptionFormatter
from zane_api.serializers import URLDomainField, URLPathField


class ComposeStackChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComposeStackChange
        fields = [
            "id",
            "type",
            "field",
            "new_value",
            "old_value",
            "item_id",
        ]


class ComposeStackEnvOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComposeStackEnvOverride
        fields = [
            "id",
            "key",
            "value",
        ]


class ComposeStackUrlRouteSerializer(serializers.Serializer):
    domain = serializers.CharField()
    base_path = serializers.CharField()
    strip_prefix = serializers.BooleanField()
    port = serializers.IntegerField()


class ComposeStackServiceTask(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[state.value for state in DockerSwarmTaskState]
    )
    message = serializers.CharField()
    exit_code = serializers.IntegerField(required=False, allow_null=True)


class ComposeStackServiceStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[state for state in ComposeStackServiceStatus.values()]
    )
    running_replicas = serializers.IntegerField()
    desired_replicas = serializers.IntegerField()
    updated_at = serializers.DateTimeField()
    tasks = ComposeStackServiceTask(many=True)
    mode = serializers.ChoiceField(
        choices=[
            "replicated",
            "global",
            "replicated-job",
            "global-job",
        ]  # same as docker
    )


class ComposeStackSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=255, required=False)
    unapplied_changes = ComposeStackChangeSerializer(many=True, read_only=True)
    env_overrides = ComposeStackEnvOverrideSerializer(many=True, read_only=True)
    urls = serializers.DictField(
        child=serializers.ListField(child=ComposeStackUrlRouteSerializer()),
        read_only=True,
    )
    configs = serializers.DictField(child=serializers.CharField(), read_only=True)
    service_statuses = serializers.DictField(
        child=ComposeStackServiceStatusSerializer(),
        read_only=True,
    )
    user_content = serializers.CharField(required=True, allow_blank=False)

    def validate(self, attrs: dict):
        # set a default `slug`
        fake = Faker()
        Faker.seed(time.monotonic())
        attrs["slug"] = attrs.get("slug", fake.slug()).lower()

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        project = cast(Project, self.context["project"])
        environment = cast(Environment, self.context["environment"])
        user_content = validated_data["user_content"]

        try:
            ComposeSpecProcessor.validate_compose_file_syntax(user_content)
        except ValidationError as e:
            raise serializers.ValidationError({"user_content": e.messages})

        slug = validated_data["slug"]
        if ComposeStack.objects.filter(
            slug=slug,
            project=project,
            environment=environment,
        ).exists():
            raise serializers.ValidationError(
                {
                    "slug": f"A compose stack with the slug `{slug}` already exists in this environment."
                }
            )

        stack = ComposeStack.objects.create(
            project=project,
            environment=environment,
            slug=slug,
            network_alias_prefix=f"zn-{slug}",
        )

        artifacts = ComposeSpecProcessor.compile_stack_for_deployment(
            user_content=user_content,
            stack=stack,
        )

        changes = [
            ComposeStackChange(
                stack=stack,
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
                type=ComposeStackChange.ChangeType.UPDATE,
                new_value=user_content,
            )
        ]

        changes.extend(
            [
                ComposeStackChange(
                    stack=stack,
                    field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
                    type=ComposeStackChange.ChangeType.ADD,
                    new_value=override_data.to_dict(),
                )
                for override_data in artifacts.env_overrides
            ]
        )

        ComposeStackChange.objects.bulk_create(changes)

        return stack

    class Meta:
        model = ComposeStack
        fields = [
            "id",
            "slug",
            "network_alias_prefix",
            "user_content",
            "computed_content",
            "unapplied_changes",
            "urls",
            "configs",
            "env_overrides",
            "service_statuses",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "computed_content": {"read_only": True},
            "name": {"read_only": True},
            "network_alias_prefix": {"read_only": True},
        }


class ComposeStackUpdateSerializer(ComposeStackSerializer):
    user_content = serializers.CharField(read_only=True)


class ComposeStackSnapshotSerializer(ComposeStackSerializer):
    class Meta(ComposeStackSerializer.Meta):
        fields = [
            "id",
            "hash_prefix",
            "monitor_schedule_id",
            "name",
            "slug",
            "network_alias_prefix",
            "user_content",
            "computed_content",
            "urls",
            "configs",
            "env_overrides",
        ]


class ComposeStackDeploymentSerializer(serializers.ModelSerializer):
    stack_snapshot = ComposeStackSnapshotSerializer(read_only=True)
    changes = ComposeStackChangeSerializer(many=True, read_only=True)

    class Meta:
        model = ComposeStackDeployment
        fields = [
            "hash",
            "status",
            "status_reason",
            "stack_snapshot",
            "commit_message",
            "queued_at",
            "started_at",
            "changes",
            "finished_at",
        ]


class ComposeStackDeployRequestSerializer(serializers.Serializer):
    commit_message = serializers.CharField(default="Update stack")


class ComposeStackArchiveRequestSerializer(serializers.Serializer):
    delete_configs = serializers.BooleanField(default=True)
    delete_volumes = serializers.BooleanField(default=True)


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

    def get_stack(self):
        stack: ComposeStack | None = self.context.get("stack")
        if stack is None:
            raise serializers.ValidationError("`stack` is required in context.")
        return stack

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
            stack = self.get_stack()
            existing_change_for_item_id = (
                stack.unapplied_changes.filter(
                    field=attrs["field"], item_id=attrs["item_id"]
                )
                .exclude(item_id__isnull=True)
                .first()
            )

            if existing_change_for_item_id is not None:
                raise serializers.ValidationError(
                    {
                        "item_id": f"Cannot make conflicting changes for the field `{attrs['field']}` with id `{attrs.get('item_id')}`"
                        + "\nA change already exist for the passed field and item_id:\n"
                        + json.dumps(
                            {
                                "item_id": existing_change_for_item_id.item_id,
                                "type": existing_change_for_item_id.type,
                                "new_value": existing_change_for_item_id.new_value,
                                "old_value": existing_change_for_item_id.old_value,
                            },
                            indent=2,
                            cls=EnhancedJSONEncoder,
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

    def get_stack(self):
        stack: ComposeStack | None = self.context.get("stack")
        if stack is None:
            raise serializers.ValidationError("`stack` is required in context.")
        return stack

    def get_new_value(self, obj: Any):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )

    def get_field(self, obj: Any):
        raise NotImplementedError(
            "This field should be subclassed by specific child classes"
        )


class ComposeContentFieldChangeSerializer(BaseFieldChangeSerializer):
    field = serializers.ChoiceField(
        choices=[ComposeStackChange.ChangeField.COMPOSE_CONTENT], required=True
    )
    new_value = serializers.CharField(required=True, allow_null=True)

    def validate(self, attrs: dict):
        user_content = attrs["new_value"]

        try:
            ComposeSpecProcessor.validate_compose_file_syntax(user_content)
        except ValidationError as e:
            raise serializers.ValidationError({"user_content": e.messages})

        stack = self.get_stack()

        # process compose stack to validate URLs
        computed_spec = ComposeSpecProcessor.process_compose_spec(
            user_content=user_content,
            stack=stack,
        )

        ComposeSpecProcessor.validate_and_extract_service_urls(
            spec=computed_spec,
            stack=stack,
        )

        return attrs


class ComposeEnvOverrideItemChangeSerializer(BaseChangeItemSerializer):
    new_value = EnvRequestSerializer(required=False)
    field = serializers.ChoiceField(
        choices=[ComposeStackChange.ChangeField.ENV_OVERRIDES], required=True
    )

    def validate(self, attrs: dict):
        super().validate(attrs)
        stack = self.get_stack()
        change_type = attrs["type"]
        new_value = attrs.get("new_value") or {}
        field = attrs["field"]
        if change_type in ["DELETE", "UPDATE"]:
            item_id = attrs["item_id"]

            try:
                stack.env_overrides.get(id=item_id)  # type: ignore
            except ComposeStackEnvOverride.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "item_id": [
                            f"Env override with id `{item_id}` does not exist for this service."
                        ]
                    }
                )

        # validate double `key`
        if new_value is not None:
            envs_with_same_key = stack.env_overrides.filter(
                key=new_value.get("key")
            ).count()
            envs_changes_with_same_key = stack.unapplied_changes.filter(
                field=field,
                new_value__key=new_value.get("key"),
            )
            total_envs_with_same_length = envs_with_same_key
            for env in envs_changes_with_same_key.all():
                if env.type in [
                    ComposeStackChange.ChangeType.UPDATE,
                    ComposeStackChange.ChangeType.DELETE,
                ]:
                    total_envs_with_same_length -= 1
                else:
                    total_envs_with_same_length += 1

            if total_envs_with_same_length >= 1:
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "key": "Cannot specify two environment variables overrides with the same name for this stack"
                        }
                    }
                )

        if change_type in [
            ComposeStackChange.ChangeType.ADD,
            ComposeStackChange.ChangeType.UPDATE,
        ]:
            key = new_value["key"]
            value = new_value["value"]
            # process compose stack to validate URLs
            existing_content_change = stack.unapplied_changes.filter(
                field=ComposeStackChange.ChangeField.COMPOSE_CONTENT
            ).first()
            computed_spec = ComposeSpecProcessor.process_compose_spec(
                user_content=(
                    cast(str, existing_content_change.new_value)
                    if existing_content_change is not None
                    else cast(str, stack.user_content)
                ),
                stack=stack,
                extra_env={key: value},
            )

            try:
                ComposeSpecProcessor.validate_and_extract_service_urls(
                    spec=computed_spec,
                    stack=stack,
                )
            except serializers.ValidationError as e:
                formated: dict[str, Any] = ExceptionFormatter(e, self.context, e).run()  # type: ignore
                raise serializers.ValidationError(
                    {
                        "new_value": {
                            "value": [
                                "Applying this change to the compose content causes the following error: "
                                f"`{error['attr']}: {error['detail']}`"
                                for error in formated["errors"]
                            ]
                        }
                    }
                )
        return attrs


class ComposeStackFieldChangeRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        required=True,
        choices=ComposeStackChange.ChangeField.choices,
    )


class DokployDomainSerializer(serializers.Serializer):
    path = URLPathField()
    host = URLDomainField()
    port = serializers.IntegerField(min_value=1)
    serviceName = serializers.CharField()


class DokployMountSerializer(serializers.Serializer):
    filePath = serializers.CharField(required=False)
    content = serializers.CharField(required=False)


class DokployConfigSerializer(serializers.Serializer):
    env = serializers.DictField(
        child=serializers.CharField(),
        required=False,
    )
    variables = serializers.DictField(
        child=serializers.CharField(),
        required=False,
    )
    domains = serializers.DictField(
        child=DokployDomainSerializer(many=True),
        required=False,
    )
    mounts = DokployMountSerializer(
        many=True,
        required=False,
    )


class DokployTemplateObjectSerializer(serializers.Serializer):
    compose = serializers.CharField()
    config = serializers.CharField()

    def validate_compose(self, content: str):
        try:
            parsed = yaml.safe_load(content)
            if parsed is None:
                raise ValidationError("Empty compose file")
            if not isinstance(parsed, dict):
                raise ValidationError("Compose file must be a YAML object/dictionary")
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML syntax: {str(e)}")
        else:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete_on_close=False
            ) as temp_file:
                temp_file.write(content)
                temp_file.flush()

                # validate compose syntax
                result = subprocess.run(
                    [
                        "docker",
                        "compose",  # we use `docker compose config` here because dokploy use the compose syntax
                        "-f",
                        temp_file.name,
                        "config",
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    raise serializers.ValidationError(
                        {"compose": result.stderr.strip()}
                    )

        return content

    def validate_config(self, config: str):
        try:
            parsed = tomllib.loads(config)
            if not isinstance(parsed, dict):
                raise ValidationError("config.toml must be a TOML object/dictionary")
        except tomllib.TOMLDecodeError as e:
            raise ValidationError(f"Invalid TOML syntax: {str(e)}")
        serializer = DokployConfigSerializer(data=parsed)
        serializer.is_valid(raise_exception=True)

        return config


class CreateComposeStackFromDokployTemplateRequestSerializer(serializers.Serializer):
    user_content = serializers.CharField()
    slug = serializers.SlugField()

    def validate_user_content(self, user_content: str):
        try:
            decoded_data = base64.b64decode(user_content, validate=True)
            decoded_string = decoded_data.decode("utf-8")
            serializer = DokployTemplateObjectSerializer(
                data=json.loads(decoded_string)
            )
            serializer.is_valid(raise_exception=True)
        except ValueError:
            raise serializers.ValidationError(
                {
                    "user_content": "Invalid format, it should be a base64 encoded string of a JSON object."
                }
            )
        return user_content

    def validate_slug(self, slug: str):
        project = cast(Project, self.context["project"])
        environment = cast(Environment, self.context["environment"])
        if ComposeStack.objects.filter(
            slug=slug,
            project=project,
            environment=environment,
        ).exists():
            raise serializers.ValidationError(
                {
                    "slug": f"A compose stack with the slug `{slug}` already exists in this environment."
                }
            )

        return slug

    # def validate(self, attrs: dict[str, str]):
    #     return super().validate(attrs)
