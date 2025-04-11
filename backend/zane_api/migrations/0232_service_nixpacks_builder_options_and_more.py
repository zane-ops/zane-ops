# Generated by Django 5.1.3 on 2025-04-07 19:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0231_service_static_dir_builder_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="nixpacks_builder_options",
            field=models.JSONField(null=True),
        ),
        migrations.AlterField(
            model_name="service",
            name="builder",
            field=models.CharField(
                choices=[
                    ("DOCKERFILE", "Dockerfile"),
                    ("STATIC_DIR", "Static directory"),
                    ("NIXPACKS", "Nixpacks"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
