# Generated by Django 5.0.4 on 2024-09-25 00:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0157_alter_dockerdeployment_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="url",
            name="redirect_permanent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="url",
            name="redirect_to",
            field=models.URLField(max_length=2000, null=True),
        ),
    ]