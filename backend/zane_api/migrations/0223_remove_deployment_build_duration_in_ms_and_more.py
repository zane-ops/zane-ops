# Generated by Django 5.1.3 on 2025-03-23 16:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0222_auto_20250323_0502"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="deployment",
            name="build_duration_in_ms",
        ),
        migrations.AddField(
            model_name="deployment",
            name="build_finished_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="deployment",
            name="build_started_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="deployment",
            name="ignore_build_cache",
            field=models.BooleanField(default=False),
        ),
    ]
