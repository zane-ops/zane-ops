from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import EMPTY_RESPONSE
from .. import serializers
from ..docker_operations import create_project_resources, cleanup_project_resources
from ..models import Project


class ProjectSuccessResponseSerializer(serializers.Serializer):
    projects = serializers.ProjectSerializer(many=True)


class SingleProjectSuccessResponseSerializer(serializers.Serializer):
    project = serializers.ProjectSerializer()


class ProjectListSearchFiltersSerializer(serializers.Serializer):
    SORT_CHOICES = (
        ("name_asc", _("name ascending")),
        ("updated_at_desc", _("updated_at in descending order")),
    )
    include_archived = serializers.BooleanField(required=False, default=False)
    query = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=True
    )
    sort = serializers.ChoiceField(
        choices=SORT_CHOICES, required=False, default="updated_at_desc"
    )

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
    name = serializers.CharField(max_length=255)


class ProjetCreateErrorSerializer(serializers.BaseErrorSerializer):
    name = serializers.StringListField(required=False)


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
                "name_asc": "name",
                "updated_at_desc": "-updated_at",
            }

            response = self.serializer_class(
                {
                    "projects": Project.objects.filter(
                        Q(owner=request.user, archived=params["include_archived"])
                        & (
                            Q(name__istartswith=params["query"])
                            | Q(slug__startswith=params["query"].lower())
                        )
                    )
                    .select_related("owner")
                    .order_by(sort_by_map_to_fields.get(params["sort"]))[:30],
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
            slug = slugify(data["name"])
            try:
                with transaction.atomic():
                    new_project = Project.objects.create(
                        name=data["name"], slug=slug, owner=request.user
                    )
                create_project_resources(project=new_project)
                response = self.single_serializer_class({"project": new_project})
                return Response(response.data, status=status.HTTP_201_CREATED)
            except IntegrityError:
                response = self.error_serializer_class(
                    {
                        "errors": {
                            "name": [
                                "A project with a similar slug already exist, please use another name for this project"
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
        return Response(
            {"errors": form.errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class ProjectUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class ProjetUpdateErrorSerializer(serializers.BaseErrorSerializer):
    name = serializers.StringListField(required=False)


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
                        "root": [f"A project with the slug `{slug}` does not exist"],
                    }
                }
            )
            return Response(response.data, status=status.HTTP_404_NOT_FOUND)

        form = ProjectUpdateRequestSerializer(data=request.data)
        if form.is_valid():
            project.name = form.data["name"]
            project.save()
            response = self.serializer_class({"project": project})
            return Response(response.data)

        return Response(
            {"errors": form.errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

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
            project = Project.objects.get(slug=slug)
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
            project = Project.objects.get(slug=slug, archived=False)
            cleanup_project_resources(project)
            project.archived = True
            project.save()
        except Project.DoesNotExist:
            response = self.error_serializer_class(
                {
                    "errors": {
                        "root": [
                            f"A project with the slug `{slug}` does not exist or have already been archived"
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
