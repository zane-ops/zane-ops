# Generated by Django 5.1.3 on 2025-03-16 00:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0208_archiveddockerservice_environment_id'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='dockerregistryservice',
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name='dockerregistryservice',
            name='network_alias',
            field=models.CharField(max_length=300, null=True),
        ),
        migrations.AlterField(
            model_name='gitrepositoryservice',
            name='network_alias',
            field=models.CharField(max_length=300, null=True),
        ),
        migrations.AddConstraint(
            model_name='dockerregistryservice',
            constraint=models.UniqueConstraint(fields=('slug', 'project', 'environment'), name='unique_slug_per_env_and_project'),
        ),
        migrations.AddConstraint(
            model_name='dockerregistryservice',
            constraint=models.UniqueConstraint(fields=('network_alias', 'project', 'environment'), name='unique_network_alias_per_env_and_project'),
        ),
    ]
