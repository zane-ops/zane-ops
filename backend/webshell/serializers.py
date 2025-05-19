from rest_framework import serializers
from . import models
from .validators import validate_unix_username


class CreateSSHKeyRequestSerializer(serializers.Serializer):
    user = serializers.CharField(validators=[validate_unix_username])
    slug = serializers.SlugField()


class SSHKeySerializer(serializers.ModelSerializer):
    public_key = serializers.CharField(read_only=True)

    class Meta:
        model = models.SSHKey
        fields = [
            "id",
            "user",
            "public_key",
            "slug",
            "fingerprint",
            "updated_at",
            "created_at",
        ]


class DeploymentTerminalQuerySerializer(serializers.Serializer):
    cmd = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                "/bin/sh",
                "/bin/bash",
                "/usr/bin/fish",
                "/usr/bin/zsh",
                "/usr/bin/ksh",
                "/usr/bin/tcsh",
            ],
            default="/bin/sh",
        )
    )
    user = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
    )


class DeploymentTerminalResizeSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["resize"])
    rows = serializers.IntegerField(required=True)
    cols = serializers.IntegerField(required=True)
