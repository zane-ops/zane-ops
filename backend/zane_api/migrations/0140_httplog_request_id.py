# Generated by Django 5.0.4 on 2024-07-22 03:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0139_rename_request_duration_ms_httplog_request_duration_ns"),
    ]

    operations = [
        migrations.AddField(
            model_name="httplog",
            name="request_id",
            field=models.UUIDField(null=True),
        ),
    ]
