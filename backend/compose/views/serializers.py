from rest_framework import serializers
from ..models import ComposeStack


class ComposeStackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComposeStack
        fields = ["id", "slug"]
