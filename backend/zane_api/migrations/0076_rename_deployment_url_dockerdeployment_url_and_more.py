# Generated by Django 5.0.2 on 2024-05-01 18:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0075_dockerdeployment_deployment_url_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="dockerdeployment",
            old_name="deployment_url",
            new_name="url",
        ),
        migrations.RenameField(
            model_name="gitdeployment",
            old_name="deployment_url",
            new_name="url",
        ),
    ]