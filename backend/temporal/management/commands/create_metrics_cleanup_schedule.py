import asyncio
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from ...client import get_temporalio_client
from ...schedules import CleanupAppLogsWorkflow
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
        spec=ScheduleSpec(cron_expressions=["0 0 * * *"]),  # New schedule spec
        # Keep other properties the same
        policy=schedule.policy,
        state=schedule.state,
    )

    return ScheduleUpdate(schedule=new_schedule)


async def create_metrics_cleanup_schedule():
    client = await get_temporalio_client()

    schedule_id = "daily-logs-cleanup"
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            CleanupAppLogsWorkflow.run,
            id="cleanup-app-logs",
            task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        ),
        spec=ScheduleSpec(cron_expressions=["0 0 * * *"]),
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
    help = "Create log cleanup schedule"

    def handle(self, *args, **options):
        asyncio.run(create_metrics_cleanup_schedule())
