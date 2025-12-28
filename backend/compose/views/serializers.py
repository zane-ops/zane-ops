from typing import cast
from rest_framework import serializers, pagination
from ..models import ComposeStack, ComposeStackChange
from faker import Faker
import time
from ..compose_processsor import ComposeProcessor
from zane_api.models import Project, Environment


class ComposeStackListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


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


class ComposeStackSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=255, required=False)
    unapplied_changes = ComposeStackChangeSerializer(many=True, read_only=True)

    def validate(self, attrs: dict):
        # set a default `slug`
        fake = Faker()
        Faker.seed(time.monotonic())
        attrs["slug"] = attrs.get("slug", fake.slug()).lower()

        return attrs

    def create(self, validated_data: dict):
        project = cast(Project, self.context["project"])
        environment = cast(Environment, self.context["environment"])
        stack = ComposeStack.objects.create(
            project=project,
            environment=environment,
            slug=validated_data["slug"],
        )
        stack_name = ComposeStack.generate_stack_name(stack)
        stack.stack_name = stack_name
        stack.save()

        ComposeStackChange.objects.create(
            stack=stack,
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            type=ComposeStackChange.ChangeType.UPDATE,
            new_value=dict(
                user_compose_content=validated_data["user_compose_content"],
                computed_compose_content=ComposeProcessor.process_compose_spec(
                    user_content=validated_data["user_compose_content"],
                    project_id=project.id,
                    env_id=environment.id,
                    stack_id=stack.id,
                    stack_name=stack_name,
                ),
            ),
        )
        return stack

    class Meta:
        model = ComposeStack
        fields = [
            "id",
            "slug",
            "user_compose_content",
            "computed_compose_content",
            "unapplied_changes",
            "stack_name",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "computed_compose_content": {"read_only": True},
            "stack_name": {"read_only": True},
        }
