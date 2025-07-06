from typing import cast
import requests
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView, ListAPIView
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from ..serializers import (
    CreateGitlabAppRequestSerializer,
    CreateGitlabAppResponseSerializer,
)
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema, inline_serializer

# from zane_api.utils import jprint
from zane_api.views import BadRequest
from django.conf import settings

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework import status, serializers
from zane_api.models import GitApp
from ..models import GitHubApp, GitRepository
from django_filters.rest_framework import DjangoFilterBackend


class CreateGitlabAppAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        request=CreateGitlabAppRequestSerializer,
        responses={200: CreateGitlabAppResponseSerializer},
        operation_id="createGitlabApp",
        summary="create a gitlab app",
    )
    def get(self, request: Request):
        return Response(data={}, status=status.HTTP_501_NOT_IMPLEMENTED)


class SetupGitlabAppAPIView(APIView):
    @transaction.atomic()
    @extend_schema(operation_id="setupGitlabApp", summary="Set a gitlab app")
    def get(self, request: Request):
        return Response(data={}, status=status.HTTP_501_NOT_IMPLEMENTED)
