# Generated by Django 5.0.2 on 2024-03-09 02:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0008_alter_project_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='volume',
            name='size_limit',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
