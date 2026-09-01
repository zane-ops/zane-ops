import base64
from dataclasses import dataclass
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db.models import QuerySet
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from .constants import WORKSPACE_SESSION_KEY
from .models import (
    Project,
    TokenScope,
    Workspace,
    WorkspaceApiToken,
    WorkspaceMembership,
    WorkspaceRole,
)

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
    project_ids: QuerySet | None
    # None => no scope limit (logged-in user)
    scopes: frozenset | None
    token: WorkspaceApiToken | None = None

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
            return Project.objects.filter(
                id=project_id, workspace=self.workspace
            ).exists()
        return self.project_ids.filter(id=project_id).exists()

    @classmethod
    def from_membership(cls, membership: WorkspaceMembership) -> "EffectiveAccess":
        """Session access for a plain workspace member (no token, no scopes)."""
        return cls(
            workspace=membership.workspace,
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


def request_access(request: Any) -> EffectiveAccess:
    """
    The `EffectiveAccess` that `HasWorkspace` attached to the request.

    Every workspace-scoped view lists `HasWorkspace` in its `permission_classes`,
    so by the time a handler runs `request.access` is always set — the one place
    the missing `Request.access` attribute is papered over.
    """
    return cast(EffectiveAccess, request.access)  # type: ignore[attr-defined]


def build_session_access(
    user: AbstractUser, workspace: Workspace
) -> EffectiveAccess | None:
    membership = (
        WorkspaceMembership.objects.filter(user=user, workspace=workspace)
        .select_related("workspace")
        .prefetch_related("accessible_projects")
        .first()
    )
    if membership is None:
        return None
    return EffectiveAccess.from_membership(membership)


def build_token_access(token: WorkspaceApiToken) -> EffectiveAccess | None:
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
    accessible_projects_ids_from_creator = (
        None
        if membership.role >= WorkspaceRole.MEMBER
        else set(membership.accessible_projects.values_list("id", flat=True))
    )
    accessible_project_ids_from_token = set(
        token.accessible_projects.values_list("id", flat=True)
    )

    if accessible_project_ids_from_token:
        allowed = (
            accessible_project_ids_from_token
            if accessible_projects_ids_from_creator is None
            # Only projects in common
            else accessible_project_ids_from_token.intersection(
                accessible_projects_ids_from_creator
            )
        )
        project_ids = Project.objects.filter(id__in=allowed).values_list("id")
    elif accessible_projects_ids_from_creator is None:
        project_ids = None
    else:
        project_ids = Project.objects.filter(
            id__in=accessible_projects_ids_from_creator
        ).values_list("id")

    return EffectiveAccess(
        workspace=token.workspace,
        role=role,
        project_ids=project_ids,
        scopes=frozenset(token.scopes),
        token=token,
    )


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
    access: EffectiveAccess | None = getattr(request, "access", None)
    if access is not None:
        resolved = access.role
    else:
        membership = WorkspaceMembership.objects.filter(
            user=request.user, workspace=getattr(request, "workspace", None)
        ).first()
        resolved = membership.role if membership is not None else None

    return resolved is not None and resolved >= role


class MinRolePermission(BasePermission):
    min_role: WorkspaceRole

    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        return has_min_role(request, self.min_role)


class IsWorkspaceViewer(MinRolePermission):
    min_role = WorkspaceRole.VIEWER


class IsWorkspaceMember(MinRolePermission):
    min_role = WorkspaceRole.MEMBER


class IsWorkspaceAdmin(MinRolePermission):
    min_role = WorkspaceRole.ADMIN


class IsWorkspaceOwner(MinRolePermission):
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
        access: EffectiveAccess | None = getattr(request, "access", None)
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
        access: EffectiveAccess | None = getattr(request, "access", None)
        if access is None or access.token is None:
            return False
        return access.has_scope(TokenScope.DEPLOY_WRITE)


class IsInstanceOwner(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:  # type: ignore
        if not request.user or isinstance(request.user, AnonymousUser):
            return False

        return cast(AbstractUser, request.user).is_superuser
