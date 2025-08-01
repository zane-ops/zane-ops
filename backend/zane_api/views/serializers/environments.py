from rest_framework import serializers
from ...validators import validate_git_commit_sha
from ...models import Project, PreviewTemplate

# ==========================================
#               Environments               #
# ==========================================


class CreateEnvironmentRequestSerializer(serializers.Serializer):
    name = serializers.SlugField(max_length=255)


class CloneEnvironmentRequestSerializer(serializers.Serializer):
    deploy_services = serializers.BooleanField(default=False, required=False)
    name = serializers.SlugField(max_length=255)


# ==========================================
#           Preview Environments           #
# ==========================================


class TriggerPreviewEnvRequestSerializer(serializers.Serializer):
    branch_name = serializers.CharField()
    commit_sha = serializers.CharField(
        default="HEAD", validators=[validate_git_commit_sha]
    )
    template = serializers.CharField(required=False)

    def validate_template(self, value: str):
        project: Project | None = self.context.get("project")
        if project is None:
            raise serializers.ValidationError("`project` is required in context.")

        try:
            project.preview_templates.get(name=value)
        except PreviewTemplate.DoesNotExist:
            raise serializers.ValidationError(
                f"The preview template `{value}` does not exist in this project"
            )

        return value
