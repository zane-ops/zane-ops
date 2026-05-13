from rest_framework import serializers


class SwitchWorkspaceRequestSerializer(serializers.Serializer):
    workspace_id = serializers.CharField()
