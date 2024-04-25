# Generated by Django 5.0.2 on 2024-04-25 18:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0064_dockerdeployment_deployment_status_reason_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="dockerdeployment",
            old_name="is_production",
            new_name="is_current_production",
        ),
        migrations.RemoveField(
            model_name="gitdeployment",
            name="is_production",
        ),
        migrations.AddField(
            model_name="gitdeployment",
            name="deployment_environment",
            field=models.CharField(
                choices=[("PRODUCTION", "Production"), ("PREVIEW", "Preview")],
                default="PREVIEW",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="gitdeployment",
            name="is_current_production",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="dockerdeployment",
            name="deployment_status",
            field=models.CharField(
                choices=[
                    ("QUEUED", "Queued"),
                    ("STARTING", "Starting"),
                    ("CANCELLED", "Cancelled"),
                    ("HEALTHY", "Healthy"),
                    ("UNHEALTHY", "UnHealthy"),
                    ("OFFLINE", "Offline"),
                ],
                default="QUEUED",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="gitdeployment",
            name="deployment_status",
            field=models.CharField(
                choices=[
                    ("QUEUED", "Queued"),
                    ("STARTING", "Starting"),
                    ("BUILDING", "Building"),
                    ("CANCELLED", "Cancelled"),
                    ("HEALTHY", "Healthy"),
                    ("UNHEALTHY", "UnHealthy"),
                    ("OFFLINE", "Offline"),
                    ("SLEEPING", "Sleeping"),
                ],
                default="QUEUED",
                max_length=10,
            ),
        ),
    ]
