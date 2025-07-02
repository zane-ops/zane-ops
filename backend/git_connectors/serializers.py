from rest_framework import serializers

from zane_api.models import GitApp, GithubApp, GitlabApp


class GithubAppSerializer(serializers.ModelSerializer):
    is_installed = serializers.BooleanField()

    class Meta:
        model = GithubApp
        fields = ["id", "org_name", "app_name", "is_installed"]


class GitAppSerializer(serializers.ModelSerializer):
    github = GithubAppSerializer(allow_null=True)

    class Meta:
        model = GitApp
        fields = ["id", "github"]


class SetupGithubAppQuerySerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.RegexField(regex=r"^(create|install\:gh_app_[a-zA-Z0-9]+)$")
    installation_id = serializers.CharField(required=False)
