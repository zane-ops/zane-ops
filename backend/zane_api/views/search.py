from django.db.models import (
    QuerySet,
)

from drf_spectacular.utils import (
    extend_schema,
    PolymorphicProxySerializer,
)

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ResourceSearchParamSerializer,
)
from ..models import (
    Project,
    Service,
)

from .serializers import (
    ProjectSearchSerializer,
    ServiceSearchSerializer,
)


class ResouceSearchAPIView(APIView):
    @extend_schema(
        operation_id="searchResources",
        summary="search for resources (project, service ...)",
        parameters=[ResourceSearchParamSerializer],
        responses={
            200: PolymorphicProxySerializer(
                component_name="ResourceResponse",
                serializers=[
                    ServiceSearchSerializer,
                    ProjectSearchSerializer,
                ],
                resource_type_field_name="type",
                many=True,
            )
        },
    )
    def get(self, request: Request) -> Response:
        query = request.query_params.get("query", "").strip()
        projects: QuerySet[Project] = Project.objects.filter(
            slug__istartswith=query,
        )[:5]
        projects_object = [
            {
                "id": project.id,
                "slug": project.slug,
                "created_at": project.created_at,
            }
            for project in projects
        ]

        services = Service.objects.filter(slug__istartswith=query).select_related(
            "project", "environment"
        )[:5]

        services_object = [
            {
                "id": service.id,
                "slug": service.slug,
                "created_at": service.created_at,
                "project_slug": service.project.slug,
                "environment": service.environment.name,
            }
            for service in services
        ]

        return Response(
            [
                *ProjectSearchSerializer(projects_object, many=True).data,
                *ServiceSearchSerializer(services_object, many=True).data,
            ],
            status=status.HTTP_200_OK,
        )
