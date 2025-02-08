import asyncio
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from ...temporal import get_temporalio_client
from ...temporal import SystemCleanupWorkflow
from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleUpdateInput,
    ScheduleUpdate,
    ScheduleAlreadyRunningError,
)
from temporalio.service import RPCError


async def update_schedule_simple(input: ScheduleUpdateInput):
    schedule = input.description.schedule

    # Update the schedule
    new_schedule = Schedule(
        action=schedule.action,
        spec=ScheduleSpec(cron_expressions=["0 */4 * * *"]),  # New schedule spec
        # Keep other properties the same
        policy=schedule.policy,
        state=schedule.state,
    )

    return ScheduleUpdate(schedule=new_schedule)


async def create_system_cleanup_schedule():
    client = await get_temporalio_client()

    schedule_id = "system-cleanup"
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            SystemCleanupWorkflow.run,
            id="system-cleanup",
            task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        ),
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
    help = "Create system cleanup schedule"

    def handle(self, *args, **options):
        asyncio.run(create_system_cleanup_schedule())
