import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings

from console.models import SystemSettings
from temporal.schedules import CleanupAppDataWorkflow
from temporal.workflows.system import DockerSystemPruneWorkflow
from temporal.client import TemporalClient
from zane_api.utils import Colors


async def noop(): ...


async def setup_jobs():
    system = await SystemSettings.aget_or_create()

    # Delete obsolete jobs
    print("Deleting obsolete schedules...🔄")
    await asyncio.gather(
        TemporalClient.adelete_schedule(
            settings.OLD_APP_DATA_CLEANUP_SCHEDULE_ID,
            prefix=None,
        ),
        TemporalClient.adelete_schedule(
            settings.OLD_DOCKER_SYSTEM_PRUNE_SCHEDULE_ID,
            prefix=None,
        ),
        return_exceptions=True,  # Don't raise exceptions
    )
    print("Obsolete schedules deleted ✅")

    # Create new jobs
    print(
        f"Creating or updating schedule {Colors.ORANGE}{settings.APP_DATA_CLEANUP_SCHEDULE_ID}{Colors.BLUE}...🔄{Colors.ENDC}"
    )
    if settings.ENVIRONMENT == settings.PRODUCTION_ENV:
        print(
            f"Creating or updating schedule {Colors.ORANGE}{settings.DOCKER_SYSTEM_PRUNE_SCHEDULE_ID}{Colors.BLUE}...🔄{Colors.ENDC}"
        )
    await asyncio.gather(
        TemporalClient.create_or_update_schedule(
            schedule_id=settings.APP_DATA_CLEANUP_SCHEDULE_ID,
            workflow=CleanupAppDataWorkflow.run,
            schedule_cron=system.app_data_cleanup_cron_schedule,
        ),
        TemporalClient.create_or_update_schedule(
            schedule_id=settings.DOCKER_SYSTEM_PRUNE_SCHEDULE_ID,
            workflow=DockerSystemPruneWorkflow.run,
            schedule_cron=system.docker_system_prune_cron_schedule,
        )
        if settings.ENVIRONMENT == settings.PRODUCTION_ENV
        else noop(),
    )
    print("Schedules created/updated successfully ✅")


class Command(BaseCommand):
    help = "Create or update default automated schedules"

    def handle(self, *args, **options):
        asyncio.run(setup_jobs())
