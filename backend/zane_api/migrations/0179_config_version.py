# Generated by Django 5.1.3 on 2025-02-08 03:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0178_archivedconfig_archiveddockerservice_configs"),
    ]

    operations = [
        migrations.AddField(
            model_name="config",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
