from rest_framework import serializers
from rest_framework import pagination
from zane_api.models import GitApp, GithubApp, GitlabApp


class GithubAppNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = GithubApp
        fields = ["name"]


class GithubAppSerializer(serializers.ModelSerializer):
    is_installed = serializers.BooleanField()

    class Meta:
        model = GithubApp
        fields = [
            "id",
            "name",
            "installation_id",
            "app_url",
            "app_id",
            "is_installed",
            "created_at",
        ]


class GitlabAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitlabApp
        fields = ["id"]


class GitAppSerializer(serializers.ModelSerializer):
    github = GithubAppSerializer(allow_null=True)
    gitlab = GitlabAppSerializer(allow_null=True)

    class Meta:
        model = GitApp
        fields = ["id", "github", "gitlab"]


class GitAppListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


class GitRepoSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    url = serializers.URLField()
    type = serializers.ChoiceField(choices=["github", "gitlab"])
    private = serializers.BooleanField()


class GitRepoResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = GitRepoSerializer(many=True)


class GitRepoQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1)
    per_page = serializers.IntegerField(default=30)


class SetupGithubAppQuerySerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.RegexField(
        regex=rf"^(create|install\:{GithubApp.ID_PREFIX}[a-zA-Z0-9]+)$"
    )
    installation_id = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, str]):
        state = attrs["state"]
        if state.startswith("install") and attrs.get("installation_id") is None:
            raise serializers.ValidationError(
                {
                    "installation_id": [
                        "Installation ID should be provided in case of `install` state"
                    ]
                }
            )

        return attrs
