# Generated by Django 5.1.3 on 2025-03-26 03:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0229_archivedgitenvvariable"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedgitservice",
            name="command",
            field=models.TextField(blank=True, null=True),
        ),
    ]
