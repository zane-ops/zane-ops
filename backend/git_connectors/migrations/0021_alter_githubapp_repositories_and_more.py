# Generated by Django 5.2 on 2025-07-07 03:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("git_connectors", "0020_alter_githubapp_repositories_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="githubapp",
            name="repositories",
            field=models.ManyToManyField(
                related_name="githubapps", to="git_connectors.gitrepository"
            ),
        ),
        migrations.AlterField(
            model_name="gitlabapp",
            name="repositories",
            field=models.ManyToManyField(
                related_name="gitlabapps", to="git_connectors.gitrepository"
            ),
        ),
    ]
