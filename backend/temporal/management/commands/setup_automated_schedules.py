import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings

from console.models import SystemSettings
from temporal.schedules import CleanupAppDataWorkflow
from temporal.workflows.system import DockerSystemPruneWorkflow
from temporal.workflows.swarm import SwarmHealthcheckWorkflow
from temporal.client import TemporalClient
from zane_api.utils import Colors
from swarm.models import SwarmNode


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
        f"Creating or updating schedules: {Colors.ORANGE}{settings.APP_DATA_CLEANUP_SCHEDULE_ID}, {settings.SWARM_HEALTHCHECK_SCHEDULE_ID}{Colors.BLUE}...🔄{Colors.ENDC}"
    )

    schedule_task_queue = await SwarmNode.aget_main_schedule_task_queue()

    schedules = [
        TemporalClient.create_or_update_schedule_with_cron(
            schedule_id=settings.APP_DATA_CLEANUP_SCHEDULE_ID,
            workflow=CleanupAppDataWorkflow.run,
            schedule_cron=system.app_data_cleanup_cron_schedule,
            task_queue=schedule_task_queue,
        ),
        TemporalClient.create_or_update_schedule_with_cron(
            schedule_id=settings.SWARM_HEALTHCHECK_SCHEDULE_ID,
            workflow=SwarmHealthcheckWorkflow.run,
            schedule_cron=settings.SWARM_HEALTHCHECK_SCHEDULE_CRON,
            task_queue=schedule_task_queue,
        ),
    ]
    if settings.ENVIRONMENT == settings.PRODUCTION_ENV:
        print(
            f"Creating or updating schedule {Colors.ORANGE}{settings.DOCKER_SYSTEM_PRUNE_SCHEDULE_ID}{Colors.BLUE}...🔄{Colors.ENDC}"
        )
        schedules.append(
            TemporalClient.create_or_update_schedule_with_cron(
                schedule_id=settings.DOCKER_SYSTEM_PRUNE_SCHEDULE_ID,
                workflow=DockerSystemPruneWorkflow.run,
                schedule_cron=system.docker_system_prune_cron_schedule,
                task_queue=schedule_task_queue,
            )
        )

    await asyncio.gather(*schedules)
    print("Schedules created/updated successfully ✅")


class Command(BaseCommand):
    help = "Create or update default automated schedules"

    def handle(self, *args, **options):
        asyncio.run(setup_jobs())
