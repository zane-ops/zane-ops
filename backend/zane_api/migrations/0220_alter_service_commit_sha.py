# Generated by Django 5.1.3 on 2025-03-23 04:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0219_remove_service_docker_build_context_dir_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="commit_sha",
            field=models.CharField(max_length=45, null=True),
        ),
    ]
