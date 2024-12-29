from rest_framework import serializers


class RuntimeLogSerializer(serializers.Serializer):
    id = serializers.CharField()
    service_id = serializers.CharField(allow_null=True)
    deployment_id = serializers.CharField(allow_null=True)
    time = serializers.DateTimeField()
    content = serializers.JSONField(allow_null=True)
    content_text = serializers.CharField(allow_null=True, allow_blank=True)
    level = serializers.ChoiceField(choices=[("ERROR", "Error"), ("INFO", "Info")])
    source = serializers.ChoiceField(
        choices=[
            ("SYSTEM", "System Logs"),
            ("SERVICE", "Service Logs"),
        ]
    )


class RuntimeLogsSearchSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    previous = serializers.CharField(default=None, allow_null=True)
    next = serializers.CharField(default=None, allow_null=True)
    results = serializers.ListSerializer(child=RuntimeLogSerializer())
    query_time_ms = serializers.FloatField(required=False)
