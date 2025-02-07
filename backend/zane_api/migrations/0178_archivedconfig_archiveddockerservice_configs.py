# Generated by Django 5.1.3 on 2025-02-07 06:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0177_config_language"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArchivedConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("archived_at", models.DateTimeField(auto_now_add=True)),
                ("name", models.CharField(max_length=255)),
                ("mount_path", models.CharField(max_length=255)),
                ("contents", models.TextField(blank=True)),
                ("language", models.CharField(max_length=255, null=True)),
                ("original_id", models.CharField(max_length=255)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="archiveddockerservice",
            name="configs",
            field=models.ManyToManyField(to="zane_api.archivedconfig"),
        ),
    ]
