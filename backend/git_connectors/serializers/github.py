from rest_framework import serializers
from ..models import GitHubApp


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


# ========================#
#     Github webhooks     #
# ========================#


class GithubWebhookEvent:
    PING = "ping"
    INSTALLATION = "installation"
    INSTALLATION_REPOS = "installation_repositories"
    PUSH = "push"

    @classmethod
    def choices(cls):
        return [cls.PING, cls.INSTALLATION, cls.INSTALLATION_REPOS, cls.PUSH]


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


class GithubWebhookRepositoryRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    private = serializers.BooleanField()


class GithubWebhookInstallationRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["created", "suspend", "unsuspend"])
    installation = GithubWebhookInstallationBodyRequestSerializer()
    repositories = GithubWebhookRepositoryRequestSerializer(many=True)


class GithubWebhookInstallationRepositoriesRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["added", "removed"])
    installation = GithubWebhookInstallationBodyRequestSerializer()
    repositories_added = GithubWebhookRepositoryRequestSerializer(many=True)
    repositories_removed = GithubWebhookRepositoryRequestSerializer(many=True)


class SimpleGithubWebhookInstallationBodyRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class GithubWebhookCommitAuthorSerializer(serializers.Serializer):
    name = serializers.CharField()


class GithubWebhookCommitSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=40)
    message = serializers.CharField(allow_blank=True)
    author = GithubWebhookCommitAuthorSerializer()
    added = serializers.ListField(child=serializers.CharField())
    removed = serializers.ListField(child=serializers.CharField())
    modified = serializers.ListField(child=serializers.CharField())


class GithubWebhookPushRequestSerializer(serializers.Serializer):
    ref = serializers.CharField()
    installation = SimpleGithubWebhookInstallationBodyRequestSerializer()
    repository = GithubWebhookRepositoryRequestSerializer()
    head_commit = GithubWebhookCommitSerializer(allow_null=True)
    commits = GithubWebhookCommitSerializer(many=True)
    created = serializers.BooleanField(default=False)
    deleted = serializers.BooleanField(default=False)
    forced = serializers.BooleanField(default=False)
