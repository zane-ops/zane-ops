import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings

from temporal.workflows import DockerSystemPruneWorkflow
from console.models import SystemSettings
from temporal.client import TemporalClient


async def create_docker_system_prune_schedule():
    system = await SystemSettings.aget_or_create()

    await TemporalClient.create_or_update_schedule(
        schedule_id=settings.DOCKER_SYSTEM_PRUNE_SCHEDULE_ID,
        workflow=DockerSystemPruneWorkflow.run,
        schedule_cron=system.docker_system_prune_cron_schedule,
    )


class Command(BaseCommand):
    help = "Create or update docker system prune schedule"

    def handle(self, *args, **options):
        asyncio.run(create_docker_system_prune_schedule())
