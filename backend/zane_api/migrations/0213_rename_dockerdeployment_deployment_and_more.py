# Generated by Django 5.1.3 on 2025-03-21 05:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0212_rename_environmentenvvariable_sharedenvvariable'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DockerDeployment',
            new_name='Deployment',
        ),
        migrations.RemoveField(
            model_name='gitenvvariable',
            name='service',
        ),
        migrations.RenameIndex(
            model_name='deployment',
            new_name='zane_api_de_status_658ae5_idx',
            old_name='zane_api_do_status_00a3ce_idx',
        ),
        migrations.RenameIndex(
            model_name='deployment',
            new_name='zane_api_de_is_curr_05fddc_idx',
            old_name='zane_api_do_is_curr_567feb_idx',
        ),
        migrations.DeleteModel(
            name='GitEnvVariable',
        ),
    ]
