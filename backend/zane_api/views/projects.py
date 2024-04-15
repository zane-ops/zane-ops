import time

from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, inline_serializer
from faker import Faker
from rest_framework import exceptions
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE, ResourceConflict
from .. import serializers
from ..models import (
    Project,
    ArchivedProject,
    DockerRegistryService,
    ArchivedDockerService,
    PortConfiguration,
    URL,
    Volume,
)
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


class ProjectListResponseSerializer(serializers.Serializer):
    active = ActiveProjectPaginatedSerializer()
    archived = ArchivedProjectPaginatedSerializer()


class SingleProjectResponseSerializer(serializers.Serializer):
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


class ProjectsListView(APIView):
    @extend_schema(
        parameters=[
            ProjectListSearchFiltersSerializer,
        ],
        responses={
            200: ProjectListResponseSerializer,
        },
        operation_id="getProjectList",
    )
    def get(self, request: Request) -> Response:
        query_params = request.query_params.dict()
        form = ProjectListSearchFiltersSerializer(data=query_params)
        if form.is_valid(raise_exception=True):
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
                response = ProjectListResponseSerializer(
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
                response = ProjectListResponseSerializer(
                    {
                        "archived": {
                            "projects": list(page),
                            "total_count": page.paginator.count,
                        },
                        "active": {"projects": [], "total_count": 0},
                    }
                )
            return Response(response.data)

    @extend_schema(
        request=ProjectCreateRequestSerializer,
        responses={
            201: SingleProjectResponseSerializer,
            409: serializers.ErrorResponse409Serializer,
        },
        operation_id="createProject",
    )
    def post(self, request: Request) -> Response:
        form = ProjectCreateRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            data = form.data

            # To prevent collisions
            Faker.seed(time.monotonic())
            fake = Faker()
            slug = data.get("slug", fake.slug()).lower()
            try:
                with transaction.atomic():
                    new_project = Project.objects.create(slug=slug, owner=request.user)
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"A project with the slug '{slug}' already exist,"
                    f" please use another one for this project."
                )
            else:
                create_docker_resources_for_project.apply_async(
                    (slug,), task_id=new_project.create_task_id
                )
                response = SingleProjectResponseSerializer({"project": new_project})
                return Response(response.data, status=status.HTTP_201_CREATED)


class ProjectUpdateRequestSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=255)


class ProjectDetailsView(APIView):
    serializer_class = SingleProjectResponseSerializer

    @extend_schema(
        request=ProjectUpdateRequestSerializer,
        responses={
            409: serializers.ErrorResponse409Serializer,
        },
        operation_id="updateProjectName",
    )
    def patch(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug, owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )

        form = ProjectUpdateRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            try:
                project.slug = form.data["slug"]
                project.save()
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"The slug `{slug}` is already used by another project."
                )
            else:
                response = SingleProjectResponseSerializer({"project": project})
                return Response(response.data)

    @extend_schema(
        operation_id="getSingleProject",
    )
    def get(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        response = SingleProjectResponseSerializer({"project": project})
        return Response(response.data)

    @extend_schema(
        responses={
            200: inline_serializer("DeleteProjectResponseSerializer", fields={}),
        },
        operation_id="archiveSingleProject",
    )
    @transaction.atomic()
    def delete(self, request: Request, slug: str) -> Response:
        project: Project = (
            Project.objects.filter(
                slug=slug.lower(), owner=request.user
            ).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist or has already been archived"
            )

        archived_version = ArchivedProject.get_or_create_from_project(project)

        docker_service_list = (
            DockerRegistryService.objects.filter(Q(project=project))
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls", "env_variables")
        )
        id_list = []
        for service in docker_service_list:
            ArchivedDockerService.create_from_service(service, archived_version)
            id_list.append(service.id)

        PortConfiguration.objects.filter(
            Q(dockerregistryservice__id__in=id_list)
        ).delete()
        URL.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        Volume.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        docker_service_list.delete()

        delete_docker_resources_for_project.apply_async(
            kwargs=dict(archived_project_id=archived_version.id),
            task_id=project.archive_task_id,
        )
        project.delete()
        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)
