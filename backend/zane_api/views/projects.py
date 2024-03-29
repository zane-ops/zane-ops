import time

from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from faker import Faker
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import EMPTY_RESPONSE
from .. import serializers
from ..models import Project, ArchivedProject
from ..tasks import (
    create_docker_resources_for_project,
    delete_docker_resources_for_project,
)


class ActiveProjectPaginatedSerializer(serializers.Serializer):
    projects = serializers.ProjectSerializer(many=True)
    total_count = serializers.IntegerField()


class ArchivedProjectPaginatedSerializer(serializers.Serializer):
    projects = serializers.ArchivedProjectSerializer(many=True)
    total_count = serializers.IntegerField()


class ProjectSuccessResponseSerializer(serializers.Serializer):
    active = ActiveProjectPaginatedSerializer()
    archived = ArchivedProjectPaginatedSerializer()


class SingleProjectSuccessResponseSerializer(serializers.Serializer):
    project = serializers.ProjectSerializer()


class ProjectListSearchFiltersSerializer(serializers.Serializer):
    SORT_CHOICES = (
        ("slug_asc", _("slug ascending")),
        ("updated_at_desc", _("updated_at in descending order")),
    )

    STATUS_CHOICES = (
        ("archived", _("archived")),
        ("active", _("active")),
    )

    status = serializers.ChoiceField(
        choices=STATUS_CHOICES, required=False, default="active"
    )
    query = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=True
    )
    sort = serializers.ChoiceField(
        choices=SORT_CHOICES, required=False, default="updated_at_desc"
    )
    page = serializers.IntegerField(required=False, default=1)
    per_page = serializers.IntegerField(required=False, default=30)

    def validate_include_archived(self, value: str | bool):
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            return False
        return value

    def validate_sort(self, value: str | None):
        if not value:
            return self.fields["sort"].default
        return value


class ProjectCreateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255, required=False)


class ProjetCreateErrorSerializer(serializers.BaseErrorSerializer):
    slug = serializers.StringListField(required=False)


class ProjetCreateErrorResponseSerializer(serializers.Serializer):
    errors = ProjetCreateErrorSerializer()


class ProjectsListView(APIView):
    serializer_class = ProjectSuccessResponseSerializer
    single_serializer_class = SingleProjectSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = ProjetCreateErrorResponseSerializer

    @extend_schema(
        parameters=[
            ProjectListSearchFiltersSerializer,
        ],
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
        },
        operation_id="getProjectList",
    )
    def get(self, request: Request) -> Response:
        query_params = request.query_params.dict()
        form = ProjectListSearchFiltersSerializer(data=query_params)
        if form.is_valid():
            params = form.data

            sort_by_map_to_fields = {
                "slug_asc": "slug",
                "updated_at_desc": "-updated_at",
            }

            query_status = params.get("status")
            per_page = params.get("per_page")

            if query_status == "active":
                paginator = Paginator(
                    Project.objects.filter(
                        Q(owner=request.user)
                        & (Q(slug__startswith=params["query"].lower()))
                    ).order_by(sort_by_map_to_fields.get(params["sort"])),
                    per_page,
                )

                page = paginator.get_page(params["page"])
                response = self.serializer_class(
                    {
                        "active": {
                            "projects": list(page),
                            "total_count": page.paginator.count,
                        },
                        "archived": {"projects": [], "total_count": 0},
                    }
                )
            else:
                paginator = Paginator(
                    ArchivedProject.objects.filter(
                        (Q(owner=request.user) | Q(owner__isnull=True))
                        & (Q(slug__startswith=params["query"].lower()))
                    ).order_by("-archived_at"),
                    per_page,
                )
                page = paginator.get_page(params["page"])
                response = self.serializer_class(
                    {
                        "archived": {
                            "projects": list(page),
                            "total_count": page.paginator.count,
                        },
                        "active": {"projects": [], "total_count": 0},
                    }
                )
            return Response(response.data)

        # This should be unreachable
        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data={"errors": form.errors},
        )

    @extend_schema(
        request=ProjectCreateRequestSerializer,
        responses={
            201: single_serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
            409: error_serializer_class,
            500: error_serializer_class,
        },
        operation_id="createProject",
    )
    def post(self, request: Request) -> Response:
        form = ProjectCreateRequestSerializer(data=request.data)
        if form.is_valid():
            data = form.data

            # To prevent collisions
            Faker.seed(time.monotonic())
            fake = Faker()
            slug = data.get("slug", fake.slug()).lower()
            try:
                with transaction.atomic():
                    new_project = Project.objects.create(slug=slug, owner=request.user)
            except IntegrityError:
                response = self.error_serializer_class(
                    {
                        "errors": {
                            "name": [
                                f"A project with the slug '{slug}' already exist,"
                                f" please use another one for this project."
                            ]
                        }
                    }
                )
                return Response(response.data, status=status.HTTP_409_CONFLICT)
            except Exception as e:
                with transaction.atomic():
                    newly_created_project = Project.objects.get(slug=slug)
                    if newly_created_project is not None:
                        newly_created_project.delete()
                response = self.error_serializer_class(
                    {
                        "errors": {
                            "root": [str(e)],
                        }
                    }
                )
                return Response(
                    response.data, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            else:
                create_docker_resources_for_project.apply_async(
                    (slug,), task_id=new_project.create_task_id
                )
                response = self.single_serializer_class({"project": new_project})
                return Response(response.data, status=status.HTTP_201_CREATED)
        return Response(
            {"errors": form.errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class ProjectUpdateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255)


class ProjetUpdateErrorSerializer(serializers.BaseErrorSerializer):
    slug = serializers.StringListField(required=False)


class ProjectUpdateErrorResponseSerializer(serializers.Serializer):
    errors = ProjetUpdateErrorSerializer()


class DeleteProjectSuccessResponseSerializer(serializers.Serializer):
    pass


class ProjectDetailsView(APIView):
    serializer_class = SingleProjectSuccessResponseSerializer
    forbidden_serializer_class = serializers.ForbiddenResponseSerializer
    error_serializer_class = ProjectUpdateErrorResponseSerializer

    @extend_schema(
        request=ProjectUpdateRequestSerializer,
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
            404: error_serializer_class,
        },
        operation_id="updateProjectName",
    )
    def patch(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug)
        except Project.DoesNotExist:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "slug": [f"A project with the slug `{slug}` does not exist"],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)

        form = ProjectUpdateRequestSerializer(data=request.data)
        if form.is_valid():
            try:
                project.slug = form.data["slug"]
                project.save()
            except IntegrityError:
                response = self.error_serializer_class(
                    {
                        "errors": {
                            "slug": [
                                f"The slug `{slug}` is already used by another project"
                            ]
                        }
                    }
                )
                return Response(response.data, status=status.HTTP_409_CONFLICT)
            else:
                response = self.serializer_class({"project": project})
                return Response(response.data)

        response = self.error_serializer_class({"errors": form.errors})
        return Response(response.data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @extend_schema(
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            404: error_serializer_class,
        },
        operation_id="getSingleProject",
    )
    def get(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
        except Project.DoesNotExist:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [f"A project with the slug `{slug}` does not exist"],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)
        response = self.serializer_class({"project": project})
        return Response(response.data)

    @extend_schema(
        responses={
            200: DeleteProjectSuccessResponseSerializer,
            403: forbidden_serializer_class,
            404: serializers.BaseErrorResponseSerializer,
            500: serializers.BaseErrorResponseSerializer,
        },
        operation_id="archiveSingleProject",
    )
    def delete(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower(), owner=request.user)
            delete_docker_resources_for_project.apply_async(
                (project.id, project.created_at.timestamp()),
                task_id=project.archive_task_id,
            )

            ArchivedProject.objects.create(slug=project.slug, owner=project.owner)
            project.delete()
        except Project.DoesNotExist:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [
                            f"A project with the slug `{slug}` does not exist or has already been archived"
                        ],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [str(e)],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)
