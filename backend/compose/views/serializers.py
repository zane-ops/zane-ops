from typing import cast
from rest_framework import serializers
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
from zane_api.utils import DockerSwarmTaskState


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
            "service",
            "key",
            "value",
        ]


class ComposeStackUrlRouteSerializer(serializers.Serializer):
    domain = serializers.CharField()
    base_path = serializers.CharField()
    strip_prefix = serializers.BooleanField()
    port = serializers.IntegerField()


class ComposeStackServiceStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[state.name for state in DockerSwarmTaskState]
    )
    running_replicas = serializers.IntegerField()
    desired_replicas = serializers.IntegerField()
    updated_at = serializers.DateTimeField()


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

    def validate(self, attrs: dict):
        # set a default `slug`
        fake = Faker()
        Faker.seed(time.monotonic())
        attrs["slug"] = attrs.get("slug", fake.slug()).lower()

        return attrs

    def create(self, validated_data: dict):
        project = cast(Project, self.context["project"])
        environment = cast(Environment, self.context["environment"])
        user_content = validated_data["user_content"]

        try:
            ComposeSpecProcessor.validate_compose_file(user_content)
        except ValidationError as e:
            raise serializers.ValidationError({"user_content": e.messages})

        slug = validated_data["slug"]
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

        extracted_urls = ComposeSpecProcessor.extract_service_urls(
            spec=computed_spec,
            stack_id=stack.id,
        )

        extracted_configs = {
            name: config.content
            for name, config in computed_spec.configs.items()
            if config.is_derived_from_content and config.content is not None
        }

        ComposeStackChange.objects.create(
            stack=stack,
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            type=ComposeStackChange.ChangeType.UPDATE,
            new_value=dict(
                user_content=user_content,
                computed_content=ComposeSpecProcessor.generate_deployable_yaml(
                    spec=computed_spec,
                    user_content=user_content,
                    stack_id=stack.id,
                ),
                computed_spec=ComposeSpecProcessor.generate_deployable_yaml_dict(
                    spec=computed_spec,
                    user_content=user_content,
                    stack_id=stack.id,
                ),
                urls=extracted_urls,
                configs=extracted_configs,
            ),
        )

        env_overrides_data = ComposeSpecProcessor.extract_env_overrides(
            spec=computed_spec,
            stack_id=stack.id,
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
