# Generated by Django 5.0.2 on 2024-03-18 14:52

import django.db.models.deletion
import zane_api.helpers
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('zane_api', '0022_alter_dockerregistryservice_base_domain_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dockerregistryservice',
            name='base_domain',
        ),
        migrations.RemoveField(
            model_name='gitrepositoryservice',
            name='base_domain',
        ),
        migrations.CreateModel(
            name='ConfigURL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(blank=True, max_length=1000, null=True,
                                            validators=[zane_api.helpers.validate_url_domain])),
                ('base_path', models.CharField(default='/')),
            ],
            options={
                'unique_together': {('domain', 'base_path')},
            },
        ),
        migrations.AddField(
            model_name='dockerregistryservice',
            name='additional_urls',
            field=models.ManyToManyField(related_name='docker_services', to='zane_api.configurl'),
        ),
        migrations.AddField(
            model_name='dockerregistryservice',
            name='base_url',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.RESTRICT, to='zane_api.configurl'),
        ),
        migrations.AddField(
            model_name='gitrepositoryservice',
            name='additional_urls',
            field=models.ManyToManyField(related_name='git_services', to='zane_api.configurl'),
        ),
        migrations.AddField(
            model_name='gitrepositoryservice',
            name='base_url',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.RESTRICT, to='zane_api.configurl'),
        ),
    ]
