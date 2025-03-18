# Generated by Django 5.1.3 on 2025-03-14 04:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0199_auto_20250314_0308'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArchivedEnvironment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archived_at', models.DateTimeField(auto_now_add=True)),
                ('original_id', models.CharField(max_length=255)),
                ('name', models.SlugField(blank=True, max_length=255)),
                ('immutable', models.BooleanField(default=False)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='environments', to='zane_api.archivedproject')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
