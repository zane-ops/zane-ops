# Generated by Django 5.1.3 on 2025-02-09 02:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0187_alter_portconfiguration_host"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedurl",
            name="associated_port",
            field=models.PositiveIntegerField(null=True),
        ),
    ]
