# Generated by Django 5.0.4 on 2024-07-13 06:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0135_alter_httplog_options_alter_simplelog_options"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="simplelog",
            options={"ordering": ("-time",)},
        ),
    ]
