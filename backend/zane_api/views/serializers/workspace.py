from rest_framework import serializers
from ...models import (
    Project,
    TokenScope,
    WorkspaceRole,
    Workspace,
    WorkspaceMembership,
)
from typing import Sequence
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone
from ...validators import validate_new_password
import django_filters

from django.db.models import QuerySet, Q


class SwitchWorkspaceRequestSerializer(serializers.Serializer):
    workspace_id = serializers.CharField()


class RegenerateWorkspaceInvitationRequestSerializer(serializers.Serializer):
    valid_for = serializers.ChoiceField(
        choices=[
            (1, "1 day"),
            (2, "2 days"),
            (3, "3 days"),
            (4, "4 days"),
            (5, "5 days"),
            (6, "6 days"),
            (7, "7 days"),
        ],
        default=3,
    )


class WorkspaceRegisterRequestSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    password = serializers.CharField(
        min_length=8, max_length=255, validators=[validate_new_password]
    )


class WorkspaceEditPermissionsRequestSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=WorkspaceRole.choices)
    accessible_project_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Project.objects.all(),
        default=[],
    )

    def _get_workspace(self):
        workspace: Workspace | None = self.context.get("workspace")
        assert workspace is not None
        return workspace

    def validate_role(self, role: int):
        if role >= WorkspaceRole.OWNER:
            raise serializers.ValidationError(
                "The owner role cannot be assigned when inviting a user. "
                "To transfer ownership, the current workspace owner must do so from their workspace settings."
            )
        return role

    def validate_accessible_project_ids(self, projects: Sequence[Project]):
        for project in projects:
            if project.workspace != self._get_workspace():
                raise serializers.ValidationError(
                    f"Project with id `{project.id}` does not exist in this workspace."
                )
        return projects

    def validate(self, attrs: dict):
        role = attrs["role"]
        accessible_projects = attrs["accessible_project_ids"]

        if role < WorkspaceRole.MEMBER and len(accessible_projects) == 0:
            raise serializers.ValidationError(
                {
                    "accessible_project_ids": "Users with the Viewer role must be granted access to at least one project."
                }
            )
        if role >= WorkspaceRole.MEMBER:
            attrs["accessible_project_ids"] = []

        return attrs


class WorkspaceReviewInvitationResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class WorkspaceInvitationDecision:
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"

    @classmethod
    def choices(cls):
        return [
            cls.ACCEPT,
            cls.DECLINE,
        ]


class WorkspaceReviewInvitationRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=WorkspaceInvitationDecision.choices())


class InviteUserIntoWorkspaceRequestSerializer(serializers.Serializer):
    accessible_project_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Project.objects.all(),
        default=[],
    )

    valid_for = serializers.ChoiceField(
        choices=[
            (1, "1 day"),
            (2, "2 days"),
            (3, "3 days"),
            (4, "4 days"),
            (5, "5 days"),
            (6, "6 days"),
            (7, "7 days"),
        ],
        write_only=True,
        default=3,
    )
    role = serializers.ChoiceField(
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.VIEWER,
    )
    username = serializers.CharField(
        min_length=1,
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )

    def validate_role(self, role: int):
        if role >= WorkspaceRole.OWNER:
            raise serializers.ValidationError(
                "The owner role cannot be assigned when inviting a user. "
                "To transfer ownership, the current workspace owner must do so from their workspace settings."
            )
        return role

    def _get_workspace(self):
        workspace: Workspace | None = self.context.get("workspace")
        assert workspace is not None
        return workspace

    def validate_accessible_project_ids(self, projects: Sequence[Project]):
        for project in projects:
            if project.workspace != self._get_workspace():
                raise serializers.ValidationError(
                    f"Project with id `{project.id}` does not exist in this workspace."
                )
        return projects

    def validate(self, attrs: dict):
        role = attrs.get("role", WorkspaceRole.VIEWER)
        accessible_projects = attrs["accessible_project_ids"]

        if role < WorkspaceRole.MEMBER and len(accessible_projects) == 0:
            raise serializers.ValidationError(
                {
                    "accessible_project_ids": "Users with the Viewer role must be granted access to at least one project."
                }
            )
        if role >= WorkspaceRole.MEMBER:
            attrs["accessible_project_ids"] = []

        return attrs


class CreateWorkspaceApiTokenRequestSerializer(serializers.Serializer):
    """
    `POST /api/workspace/tokens` — plan §9.

    The `role` and `scopes` a requester may ask for are capped by their own
    role; the same cap is re-checked on every request (plan §4) since the
    creator can be demoted later.
    """

    name = serializers.CharField(min_length=1, max_length=255)
    role = serializers.ChoiceField(choices=WorkspaceRole.choices)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=TokenScope.choices),
        allow_empty=True,
        default=list,
    )
    accessible_project_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Project.objects.all(),
        default=[],
    )
    expires_at = serializers.DateTimeField(
        required=False, allow_null=True, default=None
    )

    def _get_workspace(self) -> Workspace:
        workspace: Workspace | None = self.context.get("workspace")
        assert workspace is not None
        return workspace

    def _get_actor_role(self) -> int:
        actor_role = self.context.get("actor_role")
        assert actor_role is not None
        return actor_role

    def validate_role(self, role: int):
        if role > self._get_actor_role():
            raise serializers.ValidationError(
                "You cannot create a token with a role higher than your own."
            )
        return role

    def validate_accessible_project_ids(self, projects: Sequence[Project]):
        for project in projects:
            if project.workspace_id != self._get_workspace().id:
                raise serializers.ValidationError(
                    f"Project with id `{project.id}` does not exist in this workspace."
                )
        return projects

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("The expiry date must be in the future.")
        return value


class UpdateWorkspaceApiTokenRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=255, required=False)


class WorkspaceTransferOwnershipResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class WorkspaceLeaveResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class WorkspaceTransferOwnershipRequestSerializer(serializers.Serializer):
    new_owner_id = serializers.IntegerField(min_value=1)


class WorkspaceMembershipFilterSet(django_filters.FilterSet):
    role = django_filters.ChoiceFilter(choices=WorkspaceRole.choices)
    query = django_filters.CharFilter(method="filter_query")

    def filter_query(self, qs: QuerySet, name: str, value: str):
        return qs.filter(
            Q(user__username__icontains=value) | Q(user__first_name__icontains=value)
        )

    class Meta:
        model = WorkspaceMembership
        fields = ["role", "query"]
