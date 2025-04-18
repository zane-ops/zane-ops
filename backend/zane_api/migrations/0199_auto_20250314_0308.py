# Generated by Django 5.1.3 on 2025-03-14 03:08

from django.db import migrations
import docker
import docker.errors

docker_client = docker.from_env()


def get_env_network_resource_name(env_id: str, project_id: str) -> str:
    return f"net-{project_id}-{env_id}"


def create_default_production_env_network(apps, schema_editor):
    Environment = apps.get_model("zane_api", "Environment")

    for env in Environment.objects.filter(name="production"):
        try:
            docker_client.networks.get(
                get_env_network_resource_name(env.id, env.project_id),
            )
        except docker.errors.NotFound:
            docker_client.networks.create(
                name=get_env_network_resource_name(env.id, env.project_id),
                scope="swarm",
                driver="overlay",
                labels={
                    "zane-managed": "true",
                    "zane-project": env.project_id,
                    "is_production": "True",
                },
                attachable=True,
            )


def remove_default_production_network(apps, schema_editor):
    Environment = apps.get_model("zane_api", "Environment")

    for env in Environment.objects.filter(name="production"):
        try:
            production_network = docker_client.networks.get(
                get_env_network_resource_name(env.id, env.project_id),
            )
        except docker.errors.NotFound:
            pass
        else:
            production_network.remove()


class Migration(migrations.Migration):

    dependencies = [
        ("zane_api", "0198_auto_20250314_0158"),
    ]

    operations = [
        migrations.RunPython(
            create_default_production_env_network,
            reverse_code=remove_default_production_network,
        ),
    ]
