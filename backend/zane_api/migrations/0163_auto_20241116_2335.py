# Generated by Django 5.0.4 on 2024-11-16 23:35

from django.db import migrations
from datetime import timedelta
from django.utils import timezone


def delete_old_logs(apps, schema_editor):
    SimpleLog = apps.get_model("zane_api", "SimpleLog")

    # Delete logs where time is older than 30 days
    SimpleLog.objects.filter(time__lt=timezone.now() - timedelta(days=30)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0162_alter_httplog_created_at_alter_simplelog_created_at"),
    ]

    operations = [
        migrations.RunPython(
            delete_old_logs,
            reverse_code=migrations.RunPython.noop,  # No reverse operation needed for deletion
        ),
    ]
