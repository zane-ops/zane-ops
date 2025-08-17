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
from ..models import Project, Service, Environment

from django.db.models import When, Case, Value, IntegerField, CharField, Q

from .serializers import (
    ProjectSearchResponseSerializer,
    ServiceSearchResponseSerializer,
    EnvironmentSearchResponseSerializer,
)


class ResouceSearchAPIView(APIView):
    @extend_schema(
        operation_id="searchResources",
        summary="search for resources (project, service, environment ...)",
        parameters=[ResourceSearchParamSerializer],
        responses={
            200: PolymorphicProxySerializer(
                component_name="ResourceResponse",
                serializers=[
                    EnvironmentSearchResponseSerializer,
                    ServiceSearchResponseSerializer,
                    ProjectSearchResponseSerializer,
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
        projects_list = [
            {
                "id": project.id,
                "slug": project.slug,
                "created_at": project.created_at,
            }
            for project in projects
        ]

        services = (
            Service.objects.filter(slug__istartswith=query)
            .select_related("project", "environment", "git_app")
            .annotate(
                is_production_service=Case(
                    When(
                        environment__name=Environment.PRODUCTION_ENV_NAME,
                        then=Value(0),
                    ),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
                git_provider=Case(
                    When(
                        Q(git_app__github__isnull=False),
                        then=Value("github"),
                    ),
                    When(
                        Q(git_app__gitlab__isnull=False),
                        then=Value("gitlab"),
                    ),
                    output_field=CharField(),
                ),
            )
            .order_by("is_production_service", "slug")[:5]
        )

        services_list = [
            {
                "id": service.id,
                "slug": service.slug,
                "created_at": service.created_at,
                "project_slug": service.project.slug,
                "environment": service.environment.name,
                "kind": service.type,
                "git_provider": service.git_provider,  # type: ignore
            }
            for service in services
        ]

        environments = Environment.objects.filter(
            Q(name__istartswith=query) & ~Q(name=Environment.PRODUCTION_ENV_NAME)
        ).select_related("project",)[:5]

        environments_list = [
            {
                "id": env.id,
                "name": env.name,
                "created_at": env.created_at,
                "project_slug": env.project.slug,
            }
            for env in environments
        ]

        return Response(
            [
                *ServiceSearchResponseSerializer(services_list, many=True).data,
                *ProjectSearchResponseSerializer(projects_list, many=True).data,
                *EnvironmentSearchResponseSerializer(environments_list, many=True).data,
            ],
            status=status.HTTP_200_OK,
        )
