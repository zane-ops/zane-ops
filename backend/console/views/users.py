from drf_spectacular.utils import extend_schema

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveDestroyAPIView
from rest_framework.views import APIView


from rest_framework import exceptions, status
from zane_api.models import Workspace
from zane_api.permissions import IsInstanceOwner, HasWorkspace
from zane_api.serializers import WorkspaceSerializer

from zane_api.views import EMPTY_PAGINATED_RESPONSE
from .serializers import (
    InstanceUserPagination,
    WorkspaceListFilterSet,
    InstanceUserFilterSet,
)
from ..serializers import (
    InstanceUserSerializer,
    WorkspaceDetailSerializer,
    PasswordResetTokenSerializer,
)
from ..models import PasswordResetToken
import secrets
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


class ListWorkspacesAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.all()
    pagination_class = InstanceUserPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = WorkspaceListFilterSet

    @extend_schema(
        summary="List all workspaces in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e


class ListInstanceUsersAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = InstanceUserSerializer
    queryset = User.objects.all()
    pagination_class = InstanceUserPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = InstanceUserFilterSet

    @extend_schema(
        summary="List all users in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e


class InstanceUserDetailAPIView(RetrieveAPIView):
    permission_classes = [HasWorkspace, IsInstanceOwner]
    serializer_class = InstanceUserSerializer
    queryset = User.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "id"


class WorkspaceDetailAPIView(RetrieveAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceDetailSerializer
    lookup_field = "pk"
    lookup_url_kwarg = "id"

    def get_queryset(self):  # type: ignore
        return Workspace.objects.prefetch_related(
            "memberships__user",
            "memberships__accessible_projects",
        )


class PasswordTokenListAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    queryset = PasswordResetToken.objects.all()
    serializer_class = PasswordResetTokenSerializer
    pagination_class = InstanceUserPagination


class PasswordTokenDetailAPIView(RetrieveDestroyAPIView):
    permission_classes = [IsInstanceOwner]
    queryset = PasswordResetToken.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "id"
    serializer_class = PasswordResetTokenSerializer

    def get_queryset(self):  # type: ignore
        return PasswordResetToken.objects.select_related("user")


class GeneratePasswordTokenAPIView(APIView):
    permission_classes = [IsInstanceOwner]

    @extend_schema(
        operation_id="generatePasswordResetToken",
        summary="Generate password reset token for user",
        responses={201: PasswordResetTokenSerializer},
    )
    def post(self, request: Request, id: int):
        if not User.objects.filter(pk=id).exists():
            raise exceptions.NotFound(f"User with `id={id}` does not exist.")

        user = User.objects.get(pk=id)

        token = PasswordResetToken.objects.filter(user=user).first()
        if token is None:
            token = PasswordResetToken(
                user=user,
                value=secrets.token_hex(16),
                expires_at=timezone.now() + timedelta(minutes=30),
            )
        else:
            token.expires_at = timezone.now() + timedelta(minutes=30)
            token.value = secrets.token_hex(16)

        token.save()

        serializer = PasswordResetTokenSerializer(token)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
