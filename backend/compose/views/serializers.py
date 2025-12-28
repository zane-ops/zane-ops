from rest_framework import serializers, pagination
from ..models import ComposeStack, ComposeStackChange
from faker import Faker
import time


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
        stack = ComposeStack.objects.create(
            project=self.context["project"],
            environment=self.context["environment"],
            slug=validated_data["slug"],
        )
        stack.stack_name = ComposeStack.generate_stack_name(stack)
        stack.save()

        ComposeStackChange.objects.create(
            stack=stack,
            field=ComposeStackChange.ChangeField.COMPOSE_CONTENT,
            type=ComposeStackChange.ChangeType.UPDATE,
            new_value=dict(
                user_compose_content=validated_data["user_compose_content"],
                computed_compose_content=validated_data["user_compose_content"],
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
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "computed_compose_content": {"read_only": True},
        }
