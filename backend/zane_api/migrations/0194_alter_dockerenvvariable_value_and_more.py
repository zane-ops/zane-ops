# Generated by Django 5.1.3 on 2025-02-13 22:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0193_alter_dockerenvvariable_value_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dockerenvvariable",
            name="value",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="gitenvvariable",
            name="value",
            field=models.TextField(blank=True),
        ),
    ]
