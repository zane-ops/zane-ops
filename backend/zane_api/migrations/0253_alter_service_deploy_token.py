# Generated by Django 5.2 on 2025-07-15 02:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "zane_api",
            "0252_rename_cleanup_queue_on_deploy_service_cleanup_queue_on_auto_deploy",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="deploy_token",
            field=models.CharField(max_length=35, null=True, unique=True),
        ),
    ]
