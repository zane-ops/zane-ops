# Generated by Django 5.0.4 on 2024-05-03 23:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0081_rename_url_deploymenturl_domain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dockerdeployment",
            name="deployment_status_reason",
            field=models.TextField(blank=True, null=True),
        ),
    ]
