import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings


from temporal.client import TemporalClient


async def delete_schedules():
    await asyncio.gather(
        TemporalClient.adelete_schedule(
            settings.APP_DATA_CLEANUP_SCHEDULE_ID,
            prefix=None,
        ),
        TemporalClient.adelete_schedule(
            settings.OLD_DOCKER_SYSTEM_PRUNE_SCHEDULE_ID,
            prefix=None,
        ),
        return_exceptions=True,
    )


class Command(BaseCommand):
    help = "Delete old schedules that are used for cleanup"

    def handle(self, *args, **options):
        asyncio.run(delete_schedules())
