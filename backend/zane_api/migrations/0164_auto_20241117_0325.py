# Generated by Django 5.0.4 on 2024-11-17 03:25

from django.db import migrations
from django.db.models import Q
from django.db.models import F, Func, Value


class Cast(Func):
    function = "CAST"
    template = "%(expressions)s::%(db_type)s"

    def __init__(self, expression, db_type, **extra):
        super().__init__(expression, db_type=db_type, **extra)


def populate_and_clean_content_text(apps, schema_editor):
    SimpleLog = apps.get_model("zane_api", "SimpleLog")

    # Update content_text for logs younger than 30 days, replacing escaped chars and quotes, then removing ANSI codes
    SimpleLog.objects.filter(~Q(source="PROXY"), content_text__isnull=False).update(
        content_text=Func(
            Func(
                Func(
                    Func(
                        Cast(F("content"), db_type="text"),  # Cast content JSON to text
                        Value(r"\\"),  # Replace escaped backslashes `\\` `\`
                        Value("\\"),
                        function="REPLACE",
                    ),
                    Value(r"\""),  # Replace escaped double quotes
                    Value('"'),
                    function="REPLACE",
                ),
                Value(r'^"(.*)"$'),  # Regex to match quotes at the start and end
                Value(r"\1"),  # Remove quotes, keep inner content
                function="REGEXP_REPLACE",
            ),
            Value(
                r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
            ),  # Regex pattern for ANSI codes
            Value(""),  # Remove matched ANSI codes
            function="REGEXP_REPLACE",
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0163_auto_20241116_2335"),
    ]

    operations = [
        migrations.RunPython(
            populate_and_clean_content_text,
            reverse_code=migrations.RunPython.noop,  # No reverse operation needed for deletion
        ),
    ]