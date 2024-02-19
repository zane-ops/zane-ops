# Generated by Django 5.0.2 on 2024-02-19 15:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zane_api', '0003_alter_project_created_at_dockerregistryservice_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dockerregistryservice',
            name='slug',
            field=models.SlugField(max_length=255),
        ),
        migrations.AlterField(
            model_name='gitrepositoryservice',
            name='slug',
            field=models.SlugField(max_length=255),
        ),
        migrations.CreateModel(
            name='EnvVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=255)),
                ('is_for_production', models.BooleanField(default=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zane_api.project')),
            ],
        ),
        migrations.AddField(
            model_name='dockerregistryservice',
            name='env_variables',
            field=models.ManyToManyField(to='zane_api.envvariable'),
        ),
        migrations.AddField(
            model_name='gitrepositoryservice',
            name='env_variables',
            field=models.ManyToManyField(to='zane_api.envvariable'),
        ),
        migrations.CreateModel(
            name='Volume',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255)),
                ('containerPath', models.CharField(max_length=255)),
                ('dockerService', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='zane_api.dockerregistryservice')),
                ('gitService', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='zane_api.gitrepositoryservice')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zane_api.project')),
            ],
            options={
                'unique_together': {('slug', 'project')},
            },
        ),
    ]
