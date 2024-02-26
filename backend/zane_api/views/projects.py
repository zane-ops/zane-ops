from .. import serializers
from ..models import Project

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django_ratelimit.exceptions import Ratelimited
from rest_framework.views import exception_handler
from drf_spectacular.utils import extend_schema
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Q
import django.forms as forms
from django.utils.translation import gettext_lazy as _


class ProjectSuccessResponseSerializer(serializers.Serializer):
    projects = serializers.ProjectSerializer(many=True)


class ForbiddenResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


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

    def validate_include_archived(self, value):
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            elif value.lower() == "false":
                return False
        return value

    def validate_sort(self, value: str):
        if not value:
            return self.fields["sort"].default
        return value


class ProjectsListView(APIView):
    serializer_class = ProjectSuccessResponseSerializer
    forbidden_serializer_class = ForbiddenResponseSerializer
    error_serializer_class = serializers.ErrorResponseSerializer

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
    def get(self, request: Request):
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
                        Q(
                            owner=request.user,
                            archived=params["include_archived"],
                        )
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
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            data={"errors": form.errors},
        )
