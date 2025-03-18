# Generated by Django 5.1.3 on 2025-03-14 01:00

from django.db import migrations


def create_default_production_env(apps, schema_editor):
    Project = apps.get_model("zane_api", "Project")

    for project in Project.objects.all():
        project.environments.create(name="production")


def remove_all_environments(apps, schema_editor):
    Project = apps.get_model("zane_api", "Project")

    for project in Project.objects.all():
        project.environments.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0197_environment"),
    ]

    operations = [
        migrations.RunPython(
            create_default_production_env,
            reverse_code=remove_all_environments,
        ),
    ]
