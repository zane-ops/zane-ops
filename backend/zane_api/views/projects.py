import time

from django.db import IntegrityError, transaction
from django.db.models import Q, When, IntegerField, QuerySet, Sum, Case
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, inline_serializer
from faker import Faker
from rest_framework import exceptions
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE, EMPTY_PAGINATED_RESPONSE, ResourceConflict
from .serializers import (
    ProjectListPagination,
    ProjectListFilterSet,
    ArchivedProjectListFilterSet,
    ProjectCreateRequestSerializer,
    ProjectUpdateRequestSerializer,
    ServiceListFilterSet,
)
from ..models import (
    Project,
    ArchivedProject,
    DockerRegistryService,
    ArchivedDockerService,
    PortConfiguration,
    URL,
    Volume,
    DockerDeployment,
    GitDeployment,
)
from ..serializers import (
    ProjectSerializer,
    ArchivedProjectSerializer,
    ErrorResponse409Serializer,
)
from ..tasks import (
    delete_docker_resources_for_project,
    create_docker_resources_for_project,
)


class ProjectsListAPIView(ListCreateAPIView):
    serializer_class = ProjectSerializer
    pagination_class = ProjectListPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProjectListFilterSet
    queryset = (
        Project.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    def get_queryset(self) -> QuerySet[Project]:
        queryset = Project.objects.filter(owner=self.request.user).order_by(
            "-updated_at"
        )

        docker_healthy = DockerDeployment.objects.filter(
            is_current_production=True, status=DockerDeployment.DeploymentStatus.HEALTHY
        ).values("service")

        docker_total = DockerDeployment.objects.filter(
            Q(is_current_production=True)
            & (
                Q(status=GitDeployment.DeploymentStatus.HEALTHY)
                | Q(status=DockerDeployment.DeploymentStatus.UNHEALTHY)
                | Q(status=DockerDeployment.DeploymentStatus.FAILED)
            )
        ).values("service")

        queryset = queryset.annotate(
            healthy_services=Sum(
                Case(
                    When(
                        dockerregistryservice__id__in=[
                            item["service"] for item in docker_healthy
                        ],
                        then=1,
                    ),
                    output_field=IntegerField(),
                    default=0,
                )
            ),
            total_services=Sum(
                Case(
                    When(
                        Q(
                            dockerregistryservice__id__in=[
                                item["service"] for item in docker_total
                            ]
                        ),
                        then=1,
                    ),
                    output_field=IntegerField(),
                    default=0,
                )
            ),
        )

        return queryset

    @extend_schema(operation_id="getProjectList", summary="List all active projects")
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound:
            return Response(EMPTY_PAGINATED_RESPONSE)

    @extend_schema(
        request=ProjectCreateRequestSerializer,
        responses={
            409: ErrorResponse409Serializer,
            201: ProjectSerializer,
        },
        operation_id="createProject",
        summary="Create a new project",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    @transaction.atomic()
    def create(
        self, request: Request, *args, **kwargs
    ):  # don't need to `self.request` since `request` is available as a parameter.
        form = ProjectCreateRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            data = form.data

            # To prevent collisions
            Faker.seed(time.monotonic())
            fake = Faker()
            slug = data.get("slug", fake.slug()).lower()
            try:
                new_project = Project.objects.create(
                    slug=slug, owner=request.user, description=data.get("description")
                )
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"A project with the slug '{slug}' already exist,"
                    f" please use another one for this project."
                )
            else:
                transaction.on_commit(
                    lambda: create_docker_resources_for_project.apply_async(
                        (slug,), task_id=new_project.create_task_id
                    )
                )
                response = ProjectSerializer(new_project)
                return Response(response.data, status=status.HTTP_201_CREATED)


class ArchivedProjectsListAPIView(ListAPIView):
    serializer_class = ArchivedProjectSerializer
    pagination_class = ProjectListPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ArchivedProjectListFilterSet
    queryset = ArchivedProject.objects.all()

    @extend_schema(
        operation_id="getArchivedProjectList",
        summary="List archived projects",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound:
            return Response(EMPTY_PAGINATED_RESPONSE)


class ProjectDetailsView(APIView):
    serializer_class = ProjectSerializer

    @extend_schema(
        request=ProjectUpdateRequestSerializer,
        operation_id="updateProject",
        summary="Update a project",
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
                project.slug = form.data.get("slug", project.slug)
                project.description = form.data.get("description", project.description)
                project.save()
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"The slug `{slug}` is already used by another project."
                )
            else:
                response = ProjectSerializer(project)
                return Response(response.data)

    @extend_schema(operation_id="getSingleProject", summary="Get single project")
    def get(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        response = ProjectSerializer(project)
        return Response(response.data)

    @extend_schema(
        responses={
            200: inline_serializer("DeleteProjectResponseSerializer", fields={}),
        },
        operation_id="archiveSingleProject",
        summary="Archive a Project",
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
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
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

        transaction.on_commit(
            lambda: delete_docker_resources_for_project.apply_async(
                kwargs=dict(archived_project_id=archived_version.id),
                task_id=project.archive_task_id,
            )
        )
        project.delete()
        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class ProjectServiceListView(APIView):
    filter_backends = [DjangoFilterBackend]
    filterset_class = ServiceListFilterSet

    def get(self, request: Request, slug: str):
        try:
            project = Project.objects.get(slug=slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )

        # docker_services = DockerRegistryService.objects.filter(project=project)

        # Filter = ServiceListFilterSet({"slug": request.query_params.get("slug", "")})

        return Response()
