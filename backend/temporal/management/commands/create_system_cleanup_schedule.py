import asyncio
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from ...client import get_temporalio_client
from ...workflows import DockerSystemPruneWorkflow
from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleUpdateInput,
    ScheduleUpdate,
    ScheduleAlreadyRunningError,
)
from temporalio.service import RPCError
from console.models import SystemSettings


async def update_schedule_simple(input: ScheduleUpdateInput):
    schedule = input.description.schedule

    system = await SystemSettings.aget_or_create()

    # Update the schedule
    new_schedule = Schedule(
        action=schedule.action,
        spec=ScheduleSpec(
            cron_expressions=[system.docker_system_prune_cron_schedule]
        ),  # New schedule spec
        # Keep other properties the same
        policy=schedule.policy,
        state=schedule.state,
    )

    return ScheduleUpdate(schedule=new_schedule)


async def create_docker_system_purge_schedule():
    client = await get_temporalio_client()

    schedule_id = "hourly-system-cleanup"
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            DockerSystemPruneWorkflow.run,
            id="system-cleanup",
            task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        ),
        # Every 4h
        spec=ScheduleSpec(cron_expressions=["0 */4 * * *"]),
    )

    handle = client.get_schedule_handle(schedule_id)

    try:
        await handle.update(update_schedule_simple, rpc_timeout=timedelta(seconds=5))
    except RPCError:
        # probably because the schedule doesn't exist
        try:
            await client.create_schedule(
                schedule_id,
                schedule,
                rpc_timeout=timedelta(seconds=5),
            )
        except ScheduleAlreadyRunningError:
            # because the schedule already exists and is running, we can ignore it
            pass
    except ScheduleAlreadyRunningError:
        # because the schedule already exists  and is running, we can ignore it
        pass


class Command(BaseCommand):
    help = "Create docker system prune schedule"

    def handle(self, *args, **options):
        asyncio.run(create_docker_system_purge_schedule())
