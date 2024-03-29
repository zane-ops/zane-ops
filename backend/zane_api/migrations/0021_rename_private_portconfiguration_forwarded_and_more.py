# Generated by Django 5.0.2 on 2024-03-17 15:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0020_alter_portconfiguration_public'),
    ]

    operations = [
        migrations.RenameField(
            model_name='portconfiguration',
            old_name='private',
            new_name='forwarded',
        ),
        migrations.RemoveField(
            model_name='portconfiguration',
            name='public',
        ),
        migrations.AddField(
            model_name='portconfiguration',
            name='host',
            field=models.PositiveIntegerField(null=True, unique=True),
        ),
    ]
