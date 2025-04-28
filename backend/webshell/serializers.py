from rest_framework import serializers


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


class DeploymentTerminalResizeSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["resize"])
    rows = serializers.IntegerField(required=True)
    cols = serializers.IntegerField(required=True)
