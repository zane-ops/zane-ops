from typing import Any
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


class ProjectSuccessResponseSerializer(serializers.Serializer):
    projects = serializers.ProjectSerializer(many=True)


class ForbiddenResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ProjectListSearchFiltersForm(forms.Form):
    SORT_CHOICES = (
        ("name", "name"),
        ("updated_at", "updated_at"),
    )
    include_archived = forms.BooleanField(required=False, initial=False)
    query = forms.CharField(required=False, strip=True, initial="")
    sort = forms.ChoiceField(choices=SORT_CHOICES, required=False, initial="updated_at")


class ProjectsListView(APIView):
    serializer_class = ProjectSuccessResponseSerializer
    forbidden_serializer_class = ForbiddenResponseSerializer
    error_serializer_class = serializers.ErrorResponseSerializer

    @extend_schema(
        responses={
            200: serializer_class,
            403: forbidden_serializer_class,
            422: error_serializer_class,
        },
        operation_id="getProjectList",
    )
    def get(self, request: Request):
        query_params = request.query_params.dict()
        query_params["include_archived"] = (
            query_params.get("include_archived", None) is not None
        )
        form = ProjectListSearchFiltersForm(data=query_params)
        if form.is_valid():
            params = form.data
            print("params=", params)
            response = self.serializer_class(
                {
                    "projects": Project.objects.filter(
                        owner=request.user, archived=params.get("include_archived")
                    )
                    .select_related("owner")
                    .order_by(params.get("sort"))[:30],
                }
            )
            return Response(response.data)

        return Response(
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data={"errors": form.errors},
        )
