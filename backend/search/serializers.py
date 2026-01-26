import base64
import json
from rest_framework import serializers
from .dtos import RuntimeLogLevel, RuntimeLogSource
from django.core.exceptions import ValidationError


class RuntimeLogSerializer(serializers.Serializer):
    id = serializers.CharField()
    # managed services
    service_id = serializers.CharField(allow_null=True, required=False)
    deployment_id = serializers.CharField(allow_null=True, required=False)
    # compose stack
    stack_id = serializers.CharField(allow_null=True, required=False)
    stack_service_name = serializers.CharField(allow_null=True, required=False)
    # common args
    time = serializers.DateTimeField()
    timestamp = serializers.IntegerField()
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
    previous = serializers.CharField(default=None, allow_null=True)
    next = serializers.CharField(default=None, allow_null=True)
    results = serializers.ListSerializer(child=RuntimeLogSerializer())
    query_time_ms = serializers.FloatField(required=False)


class RuntimeLogsQuerySerializer(serializers.Serializer):
    deployment_id = serializers.CharField(required=False)
    service_id = serializers.CharField(required=False)
    stack_id = serializers.CharField(required=False)
    stack_service_names = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    time_before = serializers.DateTimeField(required=False)
    time_after = serializers.DateTimeField(required=False)
    query = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    source = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                RuntimeLogSource.SERVICE,
                RuntimeLogSource.SYSTEM,
                RuntimeLogSource.BUILD,
            ]
        ),
        default=[RuntimeLogSource.SERVICE],
    )
    level = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[RuntimeLogLevel.INFO, RuntimeLogLevel.ERROR]
        ),
        required=False,
    )
    per_page = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=50
    )
    cursor = serializers.CharField(required=False, allow_null=True)

    def validate_cursor(self, cursor: str | None):
        if cursor is not None:
            try:
                decoded_data = base64.b64decode(cursor, validate=True)
                decoded_string = decoded_data.decode("utf-8")
                serializer = CursorSerializer(data=json.loads(decoded_string))
                serializer.is_valid(raise_exception=True)
            except (ValidationError, ValueError):
                raise serializers.ValidationError(
                    {
                        "cursor": "Invalid cursor format, it should be a base64 encoded string of a JSON object."
                    }
                )
        return cursor


class CursorSerializer(serializers.Serializer):
    sort = serializers.ListField(required=True, child=serializers.CharField())
    order = serializers.ChoiceField(choices=["desc", "asc"], required=True)
