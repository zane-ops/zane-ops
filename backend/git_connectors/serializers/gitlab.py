from rest_framework import serializers
from ..models import GitlabApp
from django.core.cache import cache
from zane_api.validators import validate_git_commit_sha


class GitlabAppSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    is_installed = serializers.BooleanField(read_only=True)
    app_id = serializers.CharField(read_only=True)
    gitlab_url = serializers.URLField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = GitlabApp
        fields = [
            "id",
            "name",
            "app_id",
            "gitlab_url",
            "secret",
            "is_installed",
            "created_at",
            "redirect_uri",
        ]


class GitlabAppUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    app_secret = serializers.CharField()
    redirect_uri = serializers.URLField()


class GitlabAppUpdateResponseSerializer(serializers.Serializer):
    state = serializers.CharField()


class CreateGitlabAppRequestSerializer(serializers.Serializer):
    app_id = serializers.CharField()
    app_secret = serializers.CharField()
    redirect_uri = serializers.URLField()
    gitlab_url = serializers.URLField(default="https://gitlab.com")
    name = serializers.CharField()


class CreateGitlabAppResponseSerializer(serializers.Serializer):
    state = serializers.CharField()


class SetupGitlabAppQuerySerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.RegexField(
        rf"^({GitlabApp.SETUP_STATE_CACHE_PREFIX}|{GitlabApp.UPDATE_STATE_CACHE_PREFIX}):[a-zA-Z0-9]+"
    )

    def validate_state(self, state: str):
        state_in_cache = cache.get(state)
        if state_in_cache is None:
            raise serializers.ValidationError("Invalid state variable")
        return state


# ========================#
#     GitLab webhooks     #
# ========================#


class GitlabWebhookEvent:
    PUSH = "Push Hook"
    MERGE_REQUEST = "Merge Request Hook"

    @classmethod
    def choices(cls):
        return [cls.PUSH, cls.MERGE_REQUEST]


class GitlabWebhookEventSerializer(serializers.Serializer):
    event = serializers.ChoiceField(choices=GitlabWebhookEvent.choices())
    webhook_secret = serializers.CharField()


class GitlabWebhookCommitAuthorSerializer(serializers.Serializer):
    name = serializers.CharField()


class GitlabWebhookRepositoryRequestSerializer(serializers.Serializer):
    git_http_url = serializers.URLField()


class GitlabWebhookCommitSerializer(serializers.Serializer):
    id = serializers.CharField(validators=[validate_git_commit_sha])
    message = serializers.CharField(allow_blank=True)
    author = GitlabWebhookCommitAuthorSerializer()
    added = serializers.ListField(child=serializers.CharField())
    removed = serializers.ListField(child=serializers.CharField())
    modified = serializers.ListField(child=serializers.CharField())


# ========================#
#    GitLab Push Event    #
# ========================#


class GitlabWebhookPushEventRequestSerializer(serializers.Serializer):
    ref = serializers.CharField()
    commits = GitlabWebhookCommitSerializer(many=True)
    repository = GitlabWebhookRepositoryRequestSerializer()
    before = serializers.CharField(validators=[validate_git_commit_sha])
    after = serializers.CharField(validators=[validate_git_commit_sha])
    checkout_sha = serializers.CharField(
        validators=[validate_git_commit_sha], allow_null=True
    )


# ====================================#
#     GitLab Merge Request Event      #
# ====================================#


class GitlabMergeRequestDetailsSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            # the states we care about
            "open",
            "close",
            "update",
            "merge",
            # Ignored states
            "approval",
            "reopen",
            "approved",
            "unapproval",
            "unapproved",
        ]
    )
    state = serializers.ChoiceField(choices=["opened", "closed", "locked", "merged"])
    title = serializers.CharField()
    iid = serializers.IntegerField()
    url = serializers.URLField()
    source = GitlabWebhookRepositoryRequestSerializer()
    target = GitlabWebhookRepositoryRequestSerializer()
    target_branch = serializers.CharField()
    source_branch = serializers.CharField()
    oldrev = serializers.CharField(required=False, validators=[validate_git_commit_sha])


class GitlabMergeRequestAuthor(serializers.Serializer):
    username = serializers.CharField()


class GitlabWebhookProjectRequestSerializer(GitlabWebhookRepositoryRequestSerializer):
    id = serializers.IntegerField()


class GitlabWebhookMergeRequestEventRequestSerializer(serializers.Serializer):
    object_attributes = GitlabMergeRequestDetailsSerializer()
    project = GitlabWebhookProjectRequestSerializer()
    user = GitlabMergeRequestAuthor()
