import time

from django.db import IntegrityError, transaction
from django.db.models import (
    Q,
    When,
    IntegerField,
    QuerySet,
    Sum,
    Case,
    Prefetch,
    Count,
    OuterRef,
    Subquery,
)
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    PolymorphicProxySerializer,
)
from faker import Faker
from rest_framework import exceptions
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView
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
    DockerServiceCardSerializer,
    GitServiceCardSerializer,
    ServiceListParamSerializer,
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
    DockerDeploymentChange,
    Config,
)
from ..serializers import (
    ProjectSerializer,
    ArchivedProjectSerializer,
    ErrorResponse409Serializer,
)
from ..temporal import (
    CreateProjectResourcesWorkflow,
    ProjectDetails,
    start_workflow,
    RemoveProjectResourcesWorkflow,
    ArchivedProjectDetails,
)


class ProjectsListAPIView(ListCreateAPIView):
    serializer_class = ProjectSerializer
    pagination_class = ProjectListPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProjectListFilterSet
    queryset = (
        Project.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    def get_queryset(self) -> QuerySet[Project]:  # type: ignore
        queryset = Project.objects.filter(owner=self.request.user).order_by(
            "-updated_at"
        )

        docker_healthy = DockerDeployment.objects.filter(
            is_current_production=True, status=DockerDeployment.DeploymentStatus.HEALTHY
        ).values("service")

        docker_total = DockerDeployment.objects.filter(
            Q(is_current_production=True)
            & (
                Q(status=DockerDeployment.DeploymentStatus.UNHEALTHY)
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
            slug = data.get("slug", fake.slug()).lower()  # type: ignore
            try:
                new_project = Project.objects.create(
                    slug=slug,
                    owner=request.user,
                    description=data.get("description"),  # type: ignore
                )
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"A project with the slug '{slug}' already exist,"
                    f" please use another one for this project."
                )
            else:

                transaction.on_commit(
                    lambda: start_workflow(
                        CreateProjectResourcesWorkflow.run,
                        ProjectDetails(id=new_project.id),
                        id=new_project.create_task_id,
                    )
                )
                response = ProjectSerializer(new_project)
                return Response(response.data, status=status.HTTP_201_CREATED)

        raise NotImplementedError("should never reach here")


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
                project.slug = form.data.get("slug", project.slug)  # type: ignore
                project.description = form.data.get("description", project.description)  # type: ignore
                project.save()
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"The slug `{slug}` is already used by another project."
                )
            else:
                response = ProjectSerializer(project)
                return Response(response.data)
        raise NotImplementedError("should not reach here")

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
        project = (
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
            .select_related("project", "healthcheck")
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
        Config.objects.filter(Q(dockerregistryservice__id__in=id_list)).delete()
        docker_service_list.delete()

        transaction.on_commit(
            lambda: start_workflow(
                RemoveProjectResourcesWorkflow.run,
                ArchivedProjectDetails(
                    id=archived_version.pk, original_id=archived_version.original_id
                ),
                id=archived_version.workflow_id,
            )
        )
        project.delete()
        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class ProjectServiceListView(APIView):

    @extend_schema(
        parameters=[ServiceListParamSerializer],
        responses={
            200: PolymorphicProxySerializer(
                component_name="ServiceCardResponse",
                serializers=[
                    DockerServiceCardSerializer,
                    GitServiceCardSerializer,
                ],
                resource_type_field_name="type",
                many=True,
            )
        },
        summary="Get service list",
        description="Get all services in a project",
    )
    def get(self, request: Request, slug: str):
        try:
            project = Project.objects.get(slug=slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )

        # Prefetch related fields and use annotate to count volumes
        filters = Q(project=project)
        query = request.query_params.get("query", "")
        if query:
            filters = filters & Q(slug__icontains=query)

        docker_services = (
            DockerRegistryService.objects.filter(filters)
            .prefetch_related(
                Prefetch("urls", to_attr="url_list"),
                Prefetch(
                    "volumes", queryset=Volume.objects.only("id"), to_attr="volume_list"
                ),
            )
            .annotate(
                volume_number=Count("volumes"),
                latest_deployment_status=Subquery(
                    DockerDeployment.objects.filter(
                        Q(service_id=OuterRef("pk"))
                        & ~Q(status=DockerDeployment.DeploymentStatus.CANCELLED)
                        & Q(is_current_production=True)
                    ).values("status")[:1]
                ),
            )
        )

        service_list: list[dict] = []
        for service in docker_services:
            url = service.url_list[0] if service.url_list else None  # type: ignore
            status_map = {
                DockerDeployment.DeploymentStatus.HEALTHY: "HEALTHY",
                DockerDeployment.DeploymentStatus.UNHEALTHY: "UNHEALTHY",
                DockerDeployment.DeploymentStatus.FAILED: "FAILED",
                DockerDeployment.DeploymentStatus.REMOVED: "UNHEALTHY",
                DockerDeployment.DeploymentStatus.SLEEPING: "SLEEPING",
                DockerDeployment.DeploymentStatus.QUEUED: "DEPLOYING",
                DockerDeployment.DeploymentStatus.PREPARING: "DEPLOYING",
                DockerDeployment.DeploymentStatus.CANCELLING: "DEPLOYING",
                DockerDeployment.DeploymentStatus.STARTING: "DEPLOYING",
                DockerDeployment.DeploymentStatus.RESTARTING: "UNHEALTHY",
            }

            service_image = service.image
            if service_image is None:
                image_change = service.unapplied_changes.filter(
                    field=DockerDeploymentChange.ChangeField.SOURCE
                ).first()
                service_image = image_change.new_value["image"]  # type: ignore

            parts = service_image.split(":")
            if len(parts) == 1:
                tag = "latest"
                image = service.image
            else:
                tag = parts[-1]
                parts.pop()  # remove the tag
                image = ":".join(parts)

            service_list.append(
                DockerServiceCardSerializer(
                    dict(
                        id=service.id,
                        image=image,
                        tag=tag,
                        updated_at=service.updated_at,
                        slug=service.slug,
                        volume_number=service.volume_number,  # type: ignore
                        url=str(url) if url is not None else None,
                        status=(
                            status_map[service.latest_deployment_status]  # type: ignore
                            if service.latest_deployment_status is not None  # type: ignore
                            else "NOT_DEPLOYED_YET"
                        ),
                    )
                ).data
            )
        return Response(data=service_list)
