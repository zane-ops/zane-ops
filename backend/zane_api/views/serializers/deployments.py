import django_filters

from rest_framework import pagination

from ...models import (
    Deployment,
)

# ==============================
#       Docker deployments     #
# ==============================


class DockerServiceDeploymentFilterSet(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=Deployment.DeploymentStatus.choices
    )
    queued_at = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = Deployment
        fields = ["status", "queued_at"]


class DeploymentListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"
