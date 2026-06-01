from rest_framework import serializers
from ...models import Project, WorkspaceRole, Workspace
from typing import Sequence
from django.contrib.auth.validators import UnicodeUsernameValidator
from ...validators import validate_new_password


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


class WorkspaceAcceptInvitationRequestSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, max_length=255)

    def validate_password(self, value: str):
        has_existing_account = self.context.get("has_existing_account", False)

        if not has_existing_account:
            validate_new_password(value)
        return value


class WorkspaceAcceptInvitationResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    detail = serializers.CharField()


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
        default=WorkspaceRole.GUEST,
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
        role = attrs.get("role", WorkspaceRole.GUEST)
        accessible_projects = attrs["accessible_project_ids"]

        if role < WorkspaceRole.MEMBER and len(accessible_projects) == 0:
            raise serializers.ValidationError(
                {
                    "accessible_project_ids": "Users with the Guest role must be granted access to at least one project."
                }
            )
        if role >= WorkspaceRole.MEMBER:
            attrs["accessible_project_ids"] = []

        return attrs
