# Generated by Django 5.0.4 on 2024-08-27 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0152_remove_cron_schedule_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="archiveddockerservice",
            name="healthcheck",
            field=models.JSONField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="archiveddockerservice",
            name="resource_limits",
            field=models.JSONField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="dockerregistryservice",
            name="resource_limits",
            field=models.JSONField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="gitrepositoryservice",
            name="resource_limits",
            field=models.JSONField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="dockerdeploymentchange",
            name="field",
            field=models.CharField(
                choices=[
                    ("image", "image"),
                    ("command", "command"),
                    ("credentials", "credentials"),
                    ("healthcheck", "healthcheck"),
                    ("volumes", "volumes"),
                    ("env_variables", "env variables"),
                    ("urls", "urls"),
                    ("ports", "ports"),
                    ("resource_limits", "resource limits"),
                ],
                max_length=255,
            ),
        ),
    ]
