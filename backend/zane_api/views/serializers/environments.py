from rest_framework import serializers
from ...validators import validate_git_commit_sha

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
