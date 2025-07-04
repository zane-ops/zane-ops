from rest_framework import serializers
from zane_api.models import GitApp
from .models import GitRepository, GitHubApp, GitlabApp
import django_filters
from django.db.models import QuerySet, Q


class GithubAppSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    is_installed = serializers.BooleanField(read_only=True)
    installation_id = serializers.IntegerField(read_only=True)
    app_url = serializers.URLField(read_only=True)
    app_id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = GitHubApp
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


class GitRepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GitRepository
        fields = [
            "id",
            "owner",
            "repo",
            "url",
            "private",
        ]


class GitRepositoryListFilterSet(django_filters.FilterSet):
    query = django_filters.CharFilter(method="filter_query")

    def filter_query(self, qs: QuerySet, name: str, value: str):
        return qs.filter(Q(owner__istartswith=value) | Q(repo__istartswith=value))

    class Meta:
        model = GitRepository
        fields = ["query"]


class GitRepoQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1)
    per_page = serializers.IntegerField(default=30)


class SetupGithubAppQuerySerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.RegexField(
        regex=rf"^(create|install\:{GitHubApp.ID_PREFIX}[a-zA-Z0-9]+)$"
    )
    installation_id = serializers.IntegerField(required=False)

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


class GithubWebhookEvent:
    PING = "ping"
    INSTALLATION = "installation"
    INSTALLATION_REPOS = "installation_repositories"

    @classmethod
    def choices(cls):
        return [cls.PING, cls.INSTALLATION, cls.INSTALLATION_REPOS]


class GithubWebhookEventSerializer(serializers.Serializer):
    event = serializers.ChoiceField(choices=GithubWebhookEvent.choices())
    signature256 = serializers.CharField()


class GithubWebhookPingHookRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["App"])
    app_id = serializers.IntegerField()


class GithubWebhookPingRequestSerializer(serializers.Serializer):
    zen = serializers.CharField()
    hook = GithubWebhookPingHookRequestSerializer()


class GithubWebhookInstallationBodyRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    app_id = serializers.IntegerField()


class GithubWebhookInstallationRepositoryRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    private = serializers.BooleanField()


class GithubWebhookInstallationRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["created", "suspend", "unsuspend"])
    installation = GithubWebhookInstallationBodyRequestSerializer()
    repositories = GithubWebhookInstallationRepositoryRequestSerializer(many=True)


class GithubWebhookInstallationRepositoriesRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["added", "removed"])
    installation = GithubWebhookInstallationBodyRequestSerializer()
    repositories_added = GithubWebhookInstallationRepositoryRequestSerializer(many=True)
    repositories_removed = GithubWebhookInstallationRepositoryRequestSerializer(
        many=True
    )
