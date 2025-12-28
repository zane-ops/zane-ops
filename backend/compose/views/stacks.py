from rest_framework.generics import ListCreateAPIView
from .serializers import ComposeStackSerializer, ComposeStackListPagination
from ..models import ComposeStack
from django.db.models import QuerySet

# from drf_spectacular.utils import (
#     extend_schema,
#     # inline_serializer,
#     # PolymorphicProxySerializer,
# )
# from zane_api.serializers import ErrorResponse409Serializer
from zane_api.models import Project, Environment
from rest_framework import exceptions


class ComposeStackListAPIView(ListCreateAPIView):
    serializer_class = ComposeStackSerializer
    pagination_class = ComposeStackListPagination
    queryset = ComposeStack.objects.all()

    def get_queryset(self) -> QuerySet[ComposeStack]:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]

        try:
            project = Project.objects.get(
                slug=project_slug.lower(),
                owner=self.request.user,
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

        return (
            ComposeStack.objects.filter(
                environment=environment,
                project=project,
            )
            .all()
            .prefetch_related("changes")
        )

    def get_serializer_context(self):
        project_slug = self.kwargs["project_slug"]
        env_slug = self.kwargs["env_slug"]

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

        return dict(
            **super().get_serializer_context(),
            project=project,
            environment=environment,
        )
