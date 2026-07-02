import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings

from console.models import SystemSettings
from temporal.schedules import CleanupAppDataWorkflow
from temporal.client import TemporalClient


async def create_schedule():
    system = await SystemSettings.aget_or_create()

    await TemporalClient.create_or_update_schedule(
        schedule_id=settings.APP_DATA_CLEANUP_SCHEDULE_ID,
        workflow=CleanupAppDataWorkflow.run,
        schedule_cron=system.app_data_cleanup_cron_schedule,
    )


class Command(BaseCommand):
    help = "Create or update app metrics cleanup schedule"

    def handle(self, *args, **options):
        asyncio.run(create_schedule())
