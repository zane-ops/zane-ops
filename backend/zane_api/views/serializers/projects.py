import django_filters
from django.utils.translation import gettext_lazy as _
from django_filters import OrderingFilter

from rest_framework import serializers
from ...models import Project


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
    slug = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Project
        fields = ["slug"]


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
#       Projects Search        #
# ==============================


class ProjectSearchSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    created_at = serializers.DateTimeField(required=True)
    slug = serializers.SlugField(required=True)
    type = serializers.ChoiceField(choices=["project"], default="project")


class ServiceSearchSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    project_slug = serializers.SlugField(required=True)
    slug = serializers.SlugField(required=True)
    created_at = serializers.DateTimeField(required=True)
    type = serializers.ChoiceField(choices=["service"], default="service")
    environment = serializers.CharField(required=True)


# ==============================
#     Project Service List     #
# ==============================


class ServiceListParamSerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


class BaseServiceCardSerializer(serializers.Serializer):
    updated_at = serializers.DateTimeField(required=True)
    volume_number = serializers.IntegerField(required=True)
    slug = serializers.CharField(required=True)
    url = serializers.URLField(allow_null=True)
    STATUS_CHOICES = (
        ("HEALTHY", _("Healthy")),
        ("UNHEALTHY", _("Unhealthy")),
        ("FAILED", _("Failed")),
        ("SLEEPING", _("Sleeping")),
        ("NOT_DEPLOYED_YET", _("Not deployed yet")),
        ("DEPLOYING", _("Deploying")),
    )
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    id = serializers.CharField(required=True)


class DockerServiceCardSerializer(BaseServiceCardSerializer):
    type = serializers.ChoiceField(choices=["docker"], default="docker")
    image = serializers.CharField(required=True)
    tag = serializers.CharField(required=True)


class GitServiceCardSerializer(BaseServiceCardSerializer):
    type = serializers.ChoiceField(choices=["git"], default="git")
    repository = serializers.CharField(required=True)
    last_commit_message = serializers.CharField(required=False)
    branch = serializers.CharField(required=True)
