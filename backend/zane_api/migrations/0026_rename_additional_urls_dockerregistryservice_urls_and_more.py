# Generated by Django 5.0.2 on 2024-03-18 16:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0025_remove_dockerregistryservice_base_url_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dockerregistryservice',
            old_name='additional_urls',
            new_name='urls',
        ),
        migrations.RenameField(
            model_name='gitrepositoryservice',
            old_name='additional_urls',
            new_name='urls',
        ),
    ]
