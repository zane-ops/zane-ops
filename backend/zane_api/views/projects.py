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
from rest_framework.generics import ListCreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_PAGINATED_RESPONSE, ResourceConflict
from .serializers import (
    ProjectListPagination,
    ProjectListFilterSet,
    ProjectCreateRequestSerializer,
    ProjectUpdateRequestSerializer,
    DockerServiceCardSerializer,
    GitServiceCardSerializer,
    ServiceListParamSerializer,
)
from ..models import (
    Project,
    ArchivedProject,
    Service,
    ArchivedDockerService,
    PortConfiguration,
    URL,
    Volume,
    Deployment,
    DeploymentChange,
    Config,
    Environment,
    ArchivedGitService,
)
from ..serializers import (
    ProjectSerializer,
    ErrorResponse409Serializer,
)
from temporal.client import TemporalClient
from temporal.shared import (
    ProjectDetails,
    ArchivedProjectDetails,
    EnvironmentDetails,
)
from temporal.workflows import (
    CreateProjectResourcesWorkflow,
    RemoveProjectResourcesWorkflow,
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

        healthy_services = Deployment.objects.filter(
            is_current_production=True, status=Deployment.DeploymentStatus.HEALTHY
        ).values("service")

        total_services = Deployment.objects.filter(
            Q(is_current_production=True)
            & (
                Q(status=Deployment.DeploymentStatus.HEALTHY)
                | Q(status=Deployment.DeploymentStatus.UNHEALTHY)
                | Q(status=Deployment.DeploymentStatus.FAILED)
            )
        ).values("service")

        queryset = queryset.annotate(
            healthy_services=Sum(
                Case(
                    When(
                        services__id__in=[item["service"] for item in healthy_services],
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
                            services__id__in=[
                                item["service"] for item in total_services
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
                # Create default production environment
                new_project.environments.create(name=Environment.PRODUCTION_ENV)
            except IntegrityError:
                raise ResourceConflict(
                    detail=f"A project with the slug '{slug}' already exist,"
                    f" please use another one for this project."
                )
            else:

                transaction.on_commit(
                    lambda: TemporalClient.start_workflow(
                        CreateProjectResourcesWorkflow.run,
                        ProjectDetails(id=new_project.id),
                        id=new_project.create_task_id,
                    )
                )
                response = ProjectSerializer(new_project)
                return Response(response.data, status=status.HTTP_201_CREATED)

        raise NotImplementedError("should never reach here")


class ProjectDetailsView(APIView):
    serializer_class = ProjectSerializer

    @extend_schema(
        request=ProjectUpdateRequestSerializer,
        operation_id="updateProject",
        summary="Update a project",
    )
    def patch(self, request: Request, slug: str) -> Response:
        try:
            project = Project.objects.get(slug=slug)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )

        form = ProjectUpdateRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            try:
                project.slug = form.data.get("slug", project.slug).lower()  # type: ignore
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
            project = Project.objects.get(slug=slug)
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
            Project.objects.filter(slug=slug).select_related("archived_version")
        ).first()

        if project is None:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist or has already been archived"
            )

        archived_version = ArchivedProject.get_or_create_from_project(project)

        docker_service_list = (
            Service.objects.filter(Q(project=project))
            .select_related("project", "healthcheck")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "deployments"
            )
        )
        id_list = []
        for service in docker_service_list:
            if service.deployments.count() > 0:
                if service.type == Service.ServiceType.DOCKER_REGISTRY:
                    ArchivedDockerService.create_from_service(service, archived_version)
                else:
                    ArchivedGitService.create_from_service(service, archived_version)
                id_list.append(service.id)

        PortConfiguration.objects.filter(Q(service__id__in=id_list)).delete()
        URL.objects.filter(Q(service__id__in=id_list)).delete()
        Volume.objects.filter(Q(service__id__in=id_list)).delete()
        Config.objects.filter(Q(service__id__in=id_list)).delete()
        for service in docker_service_list:
            if service.healthcheck is not None:
                service.healthcheck.delete()
        docker_service_list.delete()

        payload = ArchivedProjectDetails(
            id=archived_version.pk,
            original_id=archived_version.original_id,
            environments=[
                EnvironmentDetails(
                    id=env.original_id,
                    name=env.name,
                    project_id=archived_version.original_id,
                )
                for env in archived_version.environments.all()
            ],
        )
        transaction.on_commit(
            lambda: TemporalClient.start_workflow(
                RemoveProjectResourcesWorkflow.run,
                payload,
                id=archived_version.workflow_id,
            )
        )
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    def get(
        self,
        request: Request,
        slug: str,
        env_slug: str = Environment.PRODUCTION_ENV,
    ):
        try:
            project = Project.objects.get(slug=slug.lower())
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )

        # Prefetch related fields and use annotate to count volumes
        filters = Q(project=project) & Q(environment=environment)
        query = request.query_params.get("query", "")
        if query:
            filters = filters & Q(slug__icontains=query)

        deployment_queryset = (
            Deployment.objects.filter(service_id=OuterRef("pk"))
            .exclude(
                status__in=[
                    Deployment.DeploymentStatus.CANCELLED,
                    Deployment.DeploymentStatus.CANCELLING,
                ]
            )
            .order_by("-updated_at")
        )

        services = (
            Service.objects.filter(filters)
            .prefetch_related(
                Prefetch("urls", to_attr="url_list"),
                Prefetch(
                    "volumes", queryset=Volume.objects.only("id"), to_attr="volume_list"
                ),
            )
            .annotate(
                volume_number=Count("volumes"),
                latest_deployment_status=Subquery(
                    deployment_queryset.values("status")[:1]
                ),
                latest_commit_message=Subquery(
                    deployment_queryset.values("commit_message")[:1]
                ),
                last_updated=Subquery(deployment_queryset.values("queued_at")[:1]),
            )
        )

        service_list: list[dict] = []
        for service in services:
            url = service.url_list[0] if service.url_list else None  # type: ignore
            status_map = {
                Deployment.DeploymentStatus.HEALTHY: "HEALTHY",
                Deployment.DeploymentStatus.UNHEALTHY: "UNHEALTHY",
                Deployment.DeploymentStatus.FAILED: "FAILED",
                Deployment.DeploymentStatus.REMOVED: "UNHEALTHY",
                Deployment.DeploymentStatus.SLEEPING: "SLEEPING",
                Deployment.DeploymentStatus.QUEUED: "DEPLOYING",
                Deployment.DeploymentStatus.PREPARING: "DEPLOYING",
                Deployment.DeploymentStatus.BUILDING: "DEPLOYING",
                Deployment.DeploymentStatus.STARTING: "DEPLOYING",
                Deployment.DeploymentStatus.RESTARTING: "UNHEALTHY",
            }

            if service.type == Service.ServiceType.DOCKER_REGISTRY:
                service_image = service.image
                if service_image is None:
                    source_change = service.unapplied_changes.filter(
                        field=DeploymentChange.ChangeField.SOURCE
                    ).first()
                    service_image = source_change.new_value["image"]  # type: ignore

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
                            updated_at=service.last_updated if service.last_updated is not None else service.created_at,  # type: ignore
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
            else:
                service_repo = service.repository_url
                branch_name = service.branch_name
                if service_repo is None or branch_name is None:
                    source_change = service.unapplied_changes.filter(
                        field=DeploymentChange.ChangeField.GIT_SOURCE
                    ).first()

                    service_repo = source_change.new_value["repository_url"]  # type: ignore
                    branch_name = source_change.new_value["branch_name"]  # type: ignore

                service_list.append(
                    GitServiceCardSerializer(
                        dict(
                            id=service.id,
                            repository=service_repo,
                            last_commit_message=service.latest_commit_message,  # type: ignore
                            branch=branch_name,
                            updated_at=service.last_updated if service.last_updated is not None else service.created_at,  # type: ignore
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

                pass
        return Response(data=service_list)
