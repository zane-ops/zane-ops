# Generated by Django 5.1.3 on 2025-02-08 22:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "zane_api",
            "0184_remove_dockerdeployment_zane_api_do_url_981d00_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddIndex(
            model_name="deploymenturl",
            index=models.Index(fields=["domain"], name="zane_api_de_domain_7cec98_idx"),
        ),
    ]
