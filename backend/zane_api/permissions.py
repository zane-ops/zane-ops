from .constants import WORKSPACE_SESSION_KEY

from .models import (
    Project,
    TokenScope,
    Workspace,
    WorkspaceApiToken,
    WorkspaceMembership,
    WorkspaceRole,
)
import base64
from dataclasses import dataclass
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from django.conf import settings
from typing import Any, Optional, cast
from django.contrib.auth.models import AnonymousUser, AbstractUser

from django.contrib.auth import get_user_model
from django.db.models import QuerySet


User = get_user_model()


@dataclass(frozen=True)
class EffectiveAccess:
    """
    The single answer to "what can this request do?", computed once by
    `HasWorkspace` and stored on `request.access`. See
    `backend/notes/api-tokens-plan.md` §2-§3.

    For a logged-in user, `scopes` and `token` are `None` and the scope check
    is a no-op. For an API token, `role` is already capped at the creator's
    current role and `project_ids` is already intersected with the creator's
    projects (plan §4).
    """

    workspace: Workspace
    role: int
    # None => every project in the workspace
    project_ids: Optional[QuerySet]
    # None => no scope limit (logged-in user)
    scopes: Optional[frozenset]
    token: Optional[WorkspaceApiToken] = None

    def has_min_role(self, role: int) -> bool:
        return self.role >= role

    def has_scope(self, scope: str) -> bool:
        return self.scopes is None or scope in self.scopes

    def accessible_project_ids(self) -> QuerySet:
        if self.project_ids is None:
            return Project.objects.filter(workspace=self.workspace).values_list("id")
        return self.project_ids

    def can_access_project(self, project_id: str) -> bool:
        if self.project_ids is None:
            return (
                Project.objects.filter(
                    id=project_id, workspace=self.workspace
                ).exists()
            )
        return self.project_ids.filter(id=project_id).exists()


def build_session_access(
    user: AbstractUser, workspace: Workspace
) -> Optional[EffectiveAccess]:
    membership = (
        WorkspaceMembership.objects.filter(user=user, workspace=workspace)
        .prefetch_related("accessible_projects")
        .first()
    )
    if membership is None:
        return None
    return EffectiveAccess(
        workspace=workspace,
        role=membership.role,
        # a Member+ reaches every project; a Viewer only their granted ones
        project_ids=(
            None
            if membership.role >= WorkspaceRole.MEMBER
            else membership.accessible_projects.values_list("id")
        ),
        scopes=None,
        token=None,
    )


def build_token_access(token: WorkspaceApiToken) -> Optional[EffectiveAccess]:
    """
    Build the access for an API-token request, applying the "a token can never
    do more than the person who made it" rule on *every* request (plan §4).

    Returns `None` if the creator is no longer a member of the workspace, which
    makes the token stop working.
    """
    membership = (
        WorkspaceMembership.objects.filter(
            user=token.created_by, workspace=token.workspace
        )
        .prefetch_related("accessible_projects")
        .first()
    )
    if membership is None:
        return None

    role = min(token.role, membership.role)

    # None => the creator can reach every project in the workspace
    creator_ids = (
        None
        if membership.role >= WorkspaceRole.MEMBER
        else set(membership.accessible_projects.values_list("id", flat=True))
    )
    token_ids = set(token.accessible_projects.values_list("id", flat=True))

    if token_ids:
        allowed = token_ids if creator_ids is None else creator_ids & token_ids
        project_ids = Project.objects.filter(id__in=allowed).values_list("id")
    elif creator_ids is None:
        project_ids = None
    else:
        project_ids = Project.objects.filter(id__in=creator_ids).values_list("id")

    return EffectiveAccess(
        workspace=token.workspace,
        role=role,
        project_ids=project_ids,
        scopes=frozenset(token.scopes),
        token=token,
    )


def _resolve_role(request: Request) -> Optional[int]:
    """
    The requester's effective role in `request.workspace`.

    Reads `request.access` when `HasWorkspace` has run; otherwise falls back to
    a direct membership query so permission classes stay usable in isolation.
    """
    access: Optional[EffectiveAccess] = getattr(request, "access", None)
    if access is not None:
        return access.role

    membership = WorkspaceMembership.objects.filter(
        user=request.user, workspace=getattr(request, "workspace", None)
    ).first()
    return membership.role if membership is not None else None


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


class HasWorkspace(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        token = request.auth if isinstance(request.auth, WorkspaceApiToken) else None
        if token is not None:
            access = build_token_access(token)
            if access is None:
                return False
            request.workspace = access.workspace  # type: ignore
            request.access = access  # type: ignore
            return True

        workspace_id = request.session.get(WORKSPACE_SESSION_KEY)

        qs = Workspace.objects.filter(memberships__user=request.user)

        if workspace_id is not None:
            qs = qs.filter(id=workspace_id)

        workspace = qs.order_by("created_at").first()

        request.workspace = workspace  # type: ignore
        if workspace is None:
            return False

        request.access = build_session_access(  # type: ignore
            cast(AbstractUser, request.user), workspace
        )
        return request.access is not None


def has_min_role(request: Request, role: WorkspaceRole):
    resolved = _resolve_role(request)
    return resolved is not None and resolved >= role


def get_accessible_projects(user: AbstractUser, workspace: Workspace):
    membership = (
        WorkspaceMembership.objects.filter(user=user, workspace=workspace)
        .prefetch_related("accessible_projects")
        .first()
    )

    queryset: QuerySet[Project, tuple[str]]

    if membership is None:
        queryset = Project.objects.filter(id__in=[]).values_list(
            "id"
        )  # No membership => no accessible projects
    else:
        if membership.role >= WorkspaceRole.MEMBER:
            queryset = Project.objects.filter(workspace=workspace).values_list("id")
        else:
            queryset = membership.accessible_projects.values_list("id")

    return queryset


async def aget_accessible_projects(user: AbstractUser, workspace: Workspace):
    membership = await (
        WorkspaceMembership.objects.filter(user=user, workspace=workspace)
        .prefetch_related("accessible_projects")
        .afirst()
    )

    queryset: QuerySet[Project, tuple[str]]

    if membership is None:
        queryset = Project.objects.filter(id__in=[]).values_list(
            "id"
        )  # No membership => no accessible projects
    else:
        if membership.role >= WorkspaceRole.MEMBER:
            queryset = Project.objects.filter(workspace=workspace).values_list("id")
        else:
            queryset = membership.accessible_projects.values_list("id")

    return queryset


class _MinRolePermission(BasePermission):
    min_role: WorkspaceRole

    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        resolved = _resolve_role(request)
        return resolved is not None and resolved >= self.min_role


class IsWorkspaceViewer(_MinRolePermission):
    min_role = WorkspaceRole.VIEWER


class IsWorkspaceMember(_MinRolePermission):
    min_role = WorkspaceRole.MEMBER


class IsWorkspaceAdmin(_MinRolePermission):
    min_role = WorkspaceRole.ADMIN


class IsWorkspaceOwner(_MinRolePermission):
    min_role = WorkspaceRole.OWNER


class HasRequiredScopes(BasePermission):
    """
    Enforces `view.required_scopes` for API-token requests (plan §6).

    - a logged-in user (`request.access.scopes is None`) always passes;
    - a token passes if it holds **any one** of the view's `required_scopes`;
    - a view with no `required_scopes` cannot be reached by a token at all —
      forgetting to annotate a view fails safe (token denied, never opened).
    """

    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        access = getattr(request, "access", None)
        if access is None or access.scopes is None:
            return True

        required = getattr(view, "required_scopes", None)
        if not required:
            return False

        return any(access.has_scope(str(scope)) for scope in required)


class HasDeployWebhookAccess(BasePermission):
    """
    Guard for the deploy webhook routes (plan §7): the request must carry an
    API token with the `deploy:write` scope. `deploy_token` in the URL is now
    only a service identifier, not a secret — the project-level check happens
    in the view once the service is known.
    """

    message = "This endpoint requires an API token with the `deploy:write` scope."

    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        access = getattr(request, "access", None)
        if access is None or access.token is None:
            return False
        return access.has_scope(TokenScope.DEPLOY_WRITE)


class IsInstanceOwner(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        return cast(AbstractUser, request.user).is_superuser
