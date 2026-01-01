from typing import cast
from rest_framework import serializers
from ..models import ComposeStack, ComposeStackChange, ComposeStackEnvOverride
from faker import Faker
import time
from ..processor import ComposeSpecProcessor
from zane_api.models import Project, Environment
from django.core.exceptions import ValidationError


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
            "stack",
            "service",
        ]


class ComposeStackUrlRouteSerializer(serializers.Serializer):
    domain = serializers.CharField()
    base_path = serializers.CharField()
    strip_prefix = serializers.BooleanField()
    port = serializers.IntegerField()


class ComposeStackSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=255, required=False)
    unapplied_changes = ComposeStackChangeSerializer(many=True, read_only=True)
    env_overrides = ComposeStackEnvOverrideSerializer(many=True, read_only=True)
    urls = serializers.DictField(child=ComposeStackUrlRouteSerializer(), read_only=True)
    configs = serializers.DictField(child=serializers.CharField(), read_only=True)

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

        stack = ComposeStack.objects.create(
            project=project,
            environment=environment,
            slug=validated_data["slug"],
        )

        computed_spec = ComposeSpecProcessor.process_compose_spec(
            user_content=user_content,
            stack=stack,
        )

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
                computed_compose_dict=ComposeSpecProcessor.generate_deployable_yaml_dict(
                    spec=computed_spec,
                    user_content=user_content,
                    stack_id=stack.id,
                ),
            ),
        )

        extracted_urls = ComposeSpecProcessor.extract_service_urls(
            spec=computed_spec,
            stack_id=stack.id,
        )

        if len(extracted_urls) > 0:
            ComposeStackChange.objects.create(
                stack=stack,
                field=ComposeStackChange.ChangeField.URLS,
                type=ComposeStackChange.ChangeType.UPDATE,
                new_value=extracted_urls,
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

        new_config_data = {
            name: config.content
            for name, config in computed_spec.configs.items()
            if config.is_derived_from_content and config.content is not None
        }

        if new_config_data:
            ComposeStackChange.objects.create(
                stack=stack,
                field=ComposeStackChange.ChangeField.CONFIGS,
                type=ComposeStackChange.ChangeType.UPDATE,
                new_value=new_config_data,
            )

        return stack

    class Meta:
        model = ComposeStack
        fields = [
            "id",
            "slug",
            "user_content",
            "computed_content",
            "unapplied_changes",
            "name",
            "urls",
            "configs",
            "env_overrides",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "computed_content": {"read_only": True},
            "name": {"read_only": True},
        }


class ComposeStackUpdateSerializer(ComposeStackSerializer):
    def update(self, instance: ComposeStack, validated_data: dict):
        return super().update(instance, validated_data)
