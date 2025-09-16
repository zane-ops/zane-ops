from io import StringIO
from typing import cast
from dotenv import dotenv_values
import requests
from rest_framework import serializers, status
from ...validators import validate_git_commit_sha
from ...models import (
    Project,
    PreviewEnvTemplate,
    SharedTemplateEnvVariable,
    Service,
    GitApp,
    Environment,
)
from ...git_client import GitClient
from ...constants import HEAD_COMMIT
from git_connectors.models import GitRepository
from ...serializers import EnvironmentSerializer
from django.db import IntegrityError
from ..base import ResourceConflict
from .common import EnvRequestSerializer

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
    branch_name = serializers.CharField(required=False)
    pr_number = serializers.IntegerField(required=False)
    commit_sha = serializers.CharField(
        default=HEAD_COMMIT, validators=[validate_git_commit_sha]
    )
    template = serializers.CharField(required=False)
    env_variables = serializers.ListSerializer(
        required=False, child=EnvRequestSerializer(), default=[]
    )

    def validate_pr_number(self, pr_number: int):
        service: Service | None = self.context.get("service")
        if service is None:
            raise serializers.ValidationError("`service` is required in context.")

        gitapp = cast(GitApp, service.git_app)

        if gitapp.github is not None:
            github = gitapp.github
            if not github.is_installed:
                raise serializers.ValidationError(
                    "This GitHub app needs to be installed before it can be used"
                )

            # Prepare the request
            base_url = "https://api.github.com/repos"
            repo_full_path = (
                cast(str, service.repository_url)
                .removeprefix("https://github.com")
                .removesuffix(".git")
            )
            url = base_url + repo_full_path + f"/pulls/{pr_number}"
            headers = {
                "Authorization": f"Bearer {github.get_access_token()}",
                "Accept": "application/vnd.github+json",
            }
            # Get existing PR
            response = requests.get(url, headers=headers)
            if response.status_code != status.HTTP_200_OK:
                raise serializers.ValidationError(
                    f"Pull Request with number `{pr_number}` does not exists does not exists on repo `{service.repository_url}`"
                )

        else:
            raise serializers.ValidationError(
                "Specifying the Pull Request number is only supported for github apps right now"
            )
        return pr_number

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
                "The specified branch does not exist on the repository."
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

    def validate(self, attrs: dict):
        if attrs.get("branch_name") is not None and attrs.get("pr_number") is not None:
            raise serializers.ValidationError(
                "Only one of `branch_name` or `pr_number` should be provided"
            )
        elif attrs.get("branch_name") is None and attrs.get("pr_number") is None:
            raise serializers.ValidationError(
                "At least one of `branch_name` or `pr_number` should be provided"
            )
        return attrs


class PreviewEnvDeployDecision:
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"

    @classmethod
    def choices(cls):
        return [
            cls.APPROVE,
            cls.DECLINE,
        ]


class ReviewPreviewEnvDeploymentRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=PreviewEnvDeployDecision.choices())


# ==========================================
#         Preview Env templates            #
# ==========================================


class SharedEnvTemplateSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        fields["id"].read_only = True
        return fields

    class Meta:
        model = SharedTemplateEnvVariable
        fields = ["id", "key", "value"]


class SimpleTemplateService(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "slug"]

    def get_fields(self):
        fields = super().get_fields()
        fields["slug"].read_only = True
        return fields


class PreviewEnvTemplateSerializer(serializers.ModelSerializer):
    variables = SharedEnvTemplateSerializer(many=True, default=[], read_only=True)
    services_to_clone_ids = serializers.PrimaryKeyRelatedField(
        many=True, write_only=True, queryset=Service.objects.all(), default=[]
    )
    services_to_clone = SimpleTemplateService(
        many=True,
        read_only=True,
    )
    base_environment_id = serializers.PrimaryKeyRelatedField(
        queryset=Environment.objects.all(),
        write_only=True,
    )
    base_environment = EnvironmentSerializer(read_only=True)
    env_variables = serializers.CharField(
        write_only=True,
        allow_blank=True,
        required=False,
    )

    def validate(self, attrs: dict):
        instance: PreviewEnvTemplate | None = self.context.get("instance")
        if attrs.get("auth_enabled"):
            errors = {}
            if attrs.get("auth_user", instance.auth_user if instance else None) is None:
                errors["auth_user"] = ["This field may not be blank."]
            if (
                attrs.get("auth_password", instance.auth_password if instance else None)
                is None
            ):
                errors["auth_password"] = ["This field may not be blank."]
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data: dict):
        """
        This is required to know how to handle manytomany fields like
        `services_to_clone`, also to add additionnal logic
        """
        project: Project = validated_data.pop("project")
        variables_data = validated_data.pop("env_variables", "")
        services_to_clone = validated_data.pop("services_to_clone_ids", [])
        base_environment = validated_data.pop("base_environment_id")
        auth_enabled: bool = validated_data.pop("auth_enabled", False)
        auth_user = validated_data.pop("auth_user", None)
        auth_password = validated_data.pop("auth_password", None)
        clone_strategy = validated_data.get(
            "clone_strategy", PreviewEnvTemplate.PreviewCloneStrategy.ALL
        )
        slug = validated_data["slug"]

        is_default: bool = validated_data.get("is_default", False)

        if base_environment.is_preview:
            raise ResourceConflict(
                "Cannot create a preview template using a preview environment as a base"
            )

        if is_default:
            project.preview_templates.update(is_default=False)

        try:
            preview_env_template = PreviewEnvTemplate.objects.create(
                base_environment=base_environment,
                project=project,
                **validated_data,
                auth_enabled=auth_enabled,
                auth_user=auth_user if auth_enabled else None,
                auth_password=auth_password if auth_enabled else None,
            )
        except IntegrityError:
            raise ResourceConflict(
                f"Preview template with slug `{slug}` already exists"
            )

        if clone_strategy == PreviewEnvTemplate.PreviewCloneStrategy.ALL:
            preview_env_template.services_to_clone.set([])
        else:
            preview_env_template.services_to_clone.set(services_to_clone)

        variables = dotenv_values(stream=StringIO(variables_data))
        for key, value in variables.items():
            SharedTemplateEnvVariable.objects.create(
                template=preview_env_template,
                key=key,
                value=value or "",
            )

        return preview_env_template

    def update(self, instance: PreviewEnvTemplate, validated_data: dict):
        variables_data = validated_data.pop("env_variables", None)
        services_to_clone: list[Service] | None = validated_data.pop(
            "services_to_clone_ids", None
        )
        base_environment: Environment | None = validated_data.pop(
            "base_environment_id", None
        )
        clone_strategy = validated_data.get("clone_strategy")

        is_default: bool = validated_data.get("is_default", instance.is_default)
        auth_enabled = validated_data.pop("auth_enabled", instance.auth_enabled)
        auth_user = validated_data.pop("auth_user", instance.auth_user)
        auth_password = validated_data.pop("auth_password", instance.auth_password)

        if is_default:
            instance.project.preview_templates.update(is_default=False)
        else:
            if (
                instance.project.preview_templates.filter(is_default=True)
                .exclude(id=instance.id)
                .count()
                == 0
            ):
                raise ResourceConflict(
                    "At least one preview template must be set as the default."
                )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if base_environment is not None:
            if base_environment.is_preview:
                raise ResourceConflict(
                    "Cannot create a preview template using a preview environment as a base"
                )
            instance.base_environment = base_environment

        if auth_enabled:
            instance.auth_user = auth_user
            instance.auth_password = auth_password

        instance.auth_enabled = auth_enabled
        instance.save()

        if clone_strategy is not None:
            if clone_strategy == PreviewEnvTemplate.PreviewCloneStrategy.ALL:
                instance.services_to_clone.set([])
            elif (
                clone_strategy == PreviewEnvTemplate.PreviewCloneStrategy.ONLY
                and services_to_clone is not None
            ):
                instance.services_to_clone.set(services_to_clone)

        if variables_data is not None:
            instance.variables.all().delete()
            variables = dotenv_values(stream=StringIO(variables_data))
            for key, value in variables.items():
                SharedTemplateEnvVariable.objects.create(
                    template=instance,
                    key=key,
                    value=value or "",
                )

        return instance

    class Meta:
        model = PreviewEnvTemplate
        fields = [
            "id",
            "slug",
            "services_to_clone",  # read
            "services_to_clone_ids",  # write
            "base_environment",  # read
            "base_environment_id",  # write
            "variables",
            "clone_strategy",
            "ttl_seconds",
            "auto_teardown",
            "is_default",
            "preview_env_limit",
            "preview_root_domain",
            "auth_enabled",
            "auth_user",
            "auth_password",
            "env_variables",
        ]
        extra_kwargs = {"id": {"read_only": True}}
