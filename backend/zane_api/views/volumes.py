from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework.generics import ListAPIView

from ..models import Project, Environment, Volume
from ..serializers import VolumeWithServiceSerializer


class AvailableVolumesListAPIView(ListAPIView):
    """
    List all volumes available in the same environment for sharing.
    These are volumes owned by other services in the same environment
    that can be referenced in SharedVolume records.
    """

    serializer_class = VolumeWithServiceSerializer
    queryset = Volume.objects.all()
    pagination_class = None

    @extend_schema(
        operation_id="listAvailableVolumes",
        summary="List available volumes for sharing",
        description="Get all volumes in the same environment that can be shared with the current service.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Volume]:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs.get("env_slug")

        try:
            project = Project.objects.get(
                slug=project_slug.lower(), owner=self.request.user
            )
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )

        # Get all volumes from services in this environment
        # Prefetch the services relation for the serializer
        return (
            Volume.objects.filter(
                services__environment=environment,
                services__project=project,
            )
            .prefetch_related("services")
            .distinct()
        )
