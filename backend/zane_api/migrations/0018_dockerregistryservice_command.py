# Generated by Django 5.0.2 on 2024-03-17 07:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0017_rename_base_docker_image_dockerregistryservice_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='dockerregistryservice',
            name='command',
            field=models.TextField(blank=True, null=True),
        ),
    ]
