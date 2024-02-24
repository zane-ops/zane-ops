from typing import Any
from .. import serializers, forms
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


class ProjectSuccessResponseSerializer(serializers.Serializer):
    projects = serializers.ProjectSerializer(many=True)


class ForbiddenResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ProjectsListView(APIView):
    serializer_class = ProjectSuccessResponseSerializer
    error_serializer_class = ForbiddenResponseSerializer

    @extend_schema(
        responses={
            200: serializer_class,
            403: error_serializer_class,
        },
        operation_id="getProjectList",
    )
    def get(self, request: Request):
        response = self.serializer_class(
            {
                "projects": Project.objects.filter(owner=request.user).select_related(
                    "owner"
                ),
            }
        )
        return Response(response.data)
