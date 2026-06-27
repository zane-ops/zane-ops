import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings

from console.models import SystemSettings
from temporal.schedules import CleanupAppMetricsWorkflow
from temporal.client import TemporalClient


async def create_metrics_cleanup_schedule():
    system = await SystemSettings.aget_or_create()

    await TemporalClient.create_or_update_schedule(
        schedule_id=settings.METRICS_CLEANUP_SCHEDULE_ID,
        workflow=CleanupAppMetricsWorkflow.run,
        schedule_cron=system.metrics_cleanup_cron_schedule,
    )


class Command(BaseCommand):
    help = "Create or update app metrics cleanup schedule"

    def handle(self, *args, **options):
        asyncio.run(create_metrics_cleanup_schedule())
