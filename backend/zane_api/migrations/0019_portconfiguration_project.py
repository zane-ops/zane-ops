# Generated by Django 5.0.2 on 2024-03-17 15:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('zane_api', '0018_dockerregistryservice_command'),
    ]

    operations = [
        migrations.AddField(
            model_name='portconfiguration',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zane_api.project'),
            preserve_default=False,
        ),
    ]
