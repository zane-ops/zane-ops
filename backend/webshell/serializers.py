from rest_framework import serializers, pagination
from . import models
import django_filters
from django_filters import OrderingFilter
from .validators import validate_unix_username


class CreateSSHKeyRequestSerializer(serializers.Serializer):
    user = serializers.CharField(validators=[validate_unix_username])
    slug = serializers.SlugField()


class SSHKeySerializer(serializers.ModelSerializer):
    public_key = serializers.CharField(read_only=True)

    class Meta:
        model = models.SSHKey
        fields = [
            "id",
            "user",
            "public_key",
            "slug",
            "updated_at",
            "created_at",
        ]


class SSHKeyListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


class SSHKeyListFilterSet(django_filters.FilterSet):
    sort_by = OrderingFilter(
        fields=["name", "updated_at"],
    )
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = models.SSHKey
        fields = ["name"]


class DeploymentTerminalQuerySerializer(serializers.Serializer):
    cmd = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                "/bin/sh",
                "/bin/bash",
                "/usr/bin/fish",
                "/usr/bin/zsh",
                "/usr/bin/ksh",
                "/usr/bin/tcsh",
            ],
            default="/bin/sh",
        )
    )
    user = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
    )


class DeploymentTerminalResizeSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["resize"])
    rows = serializers.IntegerField(required=True)
    cols = serializers.IntegerField(required=True)
