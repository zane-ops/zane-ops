from .constants import WORKSPACE_SESSION_KEY

from .models import Workspace, WorkspaceMembership, WorkspaceRole
import base64
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from django.conf import settings
from typing import Any, cast
from django.contrib.auth.models import AnonymousUser, AbstractUser

from django.contrib.auth import get_user_model

User = get_user_model()


class InternalZaneAppPermission(BasePermission):
    """
    Allow only internal zaneops apps like fluentd.
    This is so that critical internal endpoints are still secure even though they are open to the internet.
    """

    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        auth: list[str] = request.headers.get("Authorization", "").split(" ")

        if len(auth) != 2:
            return False

        _type, credentials = auth
        if _type != "Basic":
            return False

        credentials = base64.b64decode(credentials).decode("utf-8")
        return credentials == f"zaneops:{settings.SECRET_KEY}"


class IsInstanceOwner(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        return cast(AbstractUser, request.user).is_superuser


class IsWorkspaceAdmin(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        membership = WorkspaceMembership.objects.filter(
            user=request.user, workspace=request.workspace
        ).first()

        return membership is not None and membership.role >= WorkspaceRole.ADMIN


class HasWorkspace(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        workspace_id = request.session.get(WORKSPACE_SESSION_KEY)

        qs = Workspace.objects.filter(memberships__user=request.user)

        if workspace_id:
            qs = qs.filter(id=workspace_id)
        workspace = qs.earliest("created_at")
        request.workspace = workspace  # type: ignore
        return request.workspace is not None
