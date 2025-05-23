# Generated by Django 5.1.3 on 2025-01-18 02:33

from django.db import migrations
from django.db.models import F, Func, Value


def populate_client_ip(apps, schema_editor):
    HttpLog = apps.get_model("zane_api", "HttpLog")

    HttpLog.objects.filter(request_headers__icontains="X-Forwarded-For").update(
        request_ip=Func(
            Func(
                Func(
                    F("request_headers"),
                    Value("X-Forwarded-For"),
                    Value("0"),
                    function="jsonb_extract_path_text",
                ),
                function="split_part",  # PostgreSQL function to split strings
                template="%(function)s(%(expressions)s, ',', 1)",  # Take the first part before the comma
            ),
            function="inet",
        )
    )


def rollback_client_ip(apps, schema_editor):
    HttpLog = apps.get_model("zane_api", "HttpLog")

    # Clear the user_agent field
    HttpLog.objects.filter(request_headers__icontains="X-Forwarded-For").update(
        request_ip="10.0.0.2"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0171_auto_20250118_0152"),
    ]

    operations = [
        migrations.RunPython(
            populate_client_ip,
            reverse_code=rollback_client_ip,
        ),
    ]
