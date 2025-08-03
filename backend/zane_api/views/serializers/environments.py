from typing import cast
from rest_framework import serializers
from ...validators import validate_git_commit_sha
from ...models import Project, PreviewEnvTemplate, Service, GitApp
from ...git_client import GitClient
from ...constants import HEAD_COMMIT
from git_connectors.models import GitRepository

# ==========================================
#               Environments               #
# ==========================================


class CreateEnvironmentRequestSerializer(serializers.Serializer):
    name = serializers.SlugField(max_length=255)

    def validate_name(self, name: str):
        if name.startswith("preview"):
            raise serializers.ValidationError(
                "Cannot create an environment starting `preview`, it is reserved for preview environments."
            )
        return name


class UpdateEnvironmentRequestSerializer(serializers.Serializer):
    name = serializers.SlugField(max_length=255)


class CloneEnvironmentRequestSerializer(serializers.Serializer):
    deploy_services = serializers.BooleanField(default=False, required=False)
    name = serializers.SlugField(max_length=255)

    def validate_name(self, name: str):
        if name.startswith("preview"):
            raise serializers.ValidationError(
                "Cannot create an environment starting `preview`, it is reserved for preview environments."
            )
        return name


# ==========================================
#           Preview Environments           #
# ==========================================


class TriggerPreviewEnvRequestSerializer(serializers.Serializer):
    branch_name = serializers.CharField()
    commit_sha = serializers.CharField(
        default=HEAD_COMMIT, validators=[validate_git_commit_sha]
    )
    template = serializers.CharField(required=False)

    def validate_branch_name(self, branch_name: str):
        service: Service | None = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")

        git = GitClient()
        gitapp = cast(GitApp, service.git_app)

        if gitapp.github is not None:
            github = gitapp.github
            if not github.is_installed:
                raise serializers.ValidationError(
                    "This GitHub app needs to be installed before it can be used"
                )

            try:
                github.repositories.get(url=service.repository_url)
            except GitRepository.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "repository_url": [
                            f"The selected github app does not have access to the repository `{service.repository_url}`."
                        ]
                    }
                )
            computed_repository_url = github.get_authenticated_repository_url(
                cast(str, service.repository_url)
            )
        elif gitapp.gitlab is not None:
            gitlab = gitapp.gitlab
            if not gitlab.is_installed:
                raise serializers.ValidationError(
                    "This Gitlab app needs to be installed before it can be used"
                )

            try:
                gitlab.repositories.get(url=service.repository_url)
            except GitRepository.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "repository_url": [
                            f"The selected gitlab app does not have access to the repository `{service.repository_url}`."
                        ]
                    }
                )
            computed_repository_url = gitlab.get_authenticated_repository_url(
                cast(str, service.repository_url)
            )
        else:
            raise serializers.ValidationError(
                "The service should have a GitHub or GitLab app."
            )

        is_valid_repository = git.check_if_git_repository_is_valid(
            computed_repository_url, branch_name
        )
        if not is_valid_repository:
            raise serializers.ValidationError(
                {
                    "repository_url": [
                        "The specified repository or branch may not or does not exist, or the repository could be private."
                    ]
                }
            )
        return branch_name

    def validate_template(self, value: str):
        project: Project | None = self.context.get("project")
        if project is None:
            raise serializers.ValidationError("`project` is required in context.")

        try:
            project.preview_templates.get(slug=value)
        except PreviewEnvTemplate.DoesNotExist:
            raise serializers.ValidationError(
                f"The preview template `{value}` does not exist in this project"
            )

        return value
