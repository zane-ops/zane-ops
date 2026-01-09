import json
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
            ComposeSpecProcessor.validate_compose_file(user_content)
        except ValidationError as e:
            raise serializers.ValidationError({"user_content": e.messages})

        slug = validated_data["slug"]
        if ComposeStack.objects.filter(slug=slug).exists():
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

        computed_spec = ComposeSpecProcessor.process_compose_spec(
            user_content=user_content,
            stack=stack,
        )

        computed_content = ComposeSpecProcessor.generate_deployable_yaml(
            spec=computed_spec,
            user_content=user_content,
            stack_hash_prefix=stack.hash_prefix,
        )

        extracted_configs = ComposeSpecProcessor.extract_config_contents(
            spec=computed_spec
        )

        extracted_urls = ComposeSpecProcessor.validate_and_extract_service_urls(
            spec=computed_spec,
            stack=stack,
        )

        ComposeStackChange.objects.create(
            stack=stack,
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            type=ComposeStackChange.ChangeType.UPDATE,
            new_value=dict(
                user_content=user_content,
                computed_content=computed_content,
                computed_spec=yaml.safe_load(computed_content),
                urls=extracted_urls,
                configs=extracted_configs,
            ),
        )

        env_overrides_data = ComposeSpecProcessor.extract_new_env_overrides(
            spec=computed_spec
        )
        ComposeStackChange.objects.bulk_create(
            [
                ComposeStackChange(
                    stack=stack,
                    field=ComposeStackChange.ChangeField.ENV_OVERRIDES,
                    type=ComposeStackChange.ChangeType.ADD,
                    new_value=override_data,
                )
                for override_data in env_overrides_data
            ]
        )

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
    type = serializers.ChoiceField(
        choices=[
            "ADD",
            "DELETE",
            "UPDATE",
        ],
        required=True,
    )
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
    type = serializers.ChoiceField(choices=["UPDATE"], required=False, default="UPDATE")
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
            ComposeSpecProcessor.validate_compose_file(user_content)
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


class ComposeEnvOverrideItemChangeSerializer(BaseFieldChangeSerializer):
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
        return attrs


class ComposeStackFieldChangeRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(
        required=True,
        choices=ComposeStackChange.ChangeField.choices,
    )
