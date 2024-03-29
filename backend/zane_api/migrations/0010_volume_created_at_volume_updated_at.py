# Generated by Django 5.0.2 on 2024-03-09 04:36

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('zane_api', '0009_volume_size_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='volume',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='volume',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
