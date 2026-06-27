import asyncio
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from ...client import get_temporalio_client
from ...schedules import CleanupAppMetricsWorkflow
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

    print(f"Updating schedule to new CRON: `{system.metrics_cleanup_cron_schedule}`")
    # Update the schedule
    new_schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            CleanupAppMetricsWorkflow.run,
            id="whatever",
            task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        ),  # schedule.action,
        spec=ScheduleSpec(
            cron_expressions=[system.metrics_cleanup_cron_schedule]
        ),  # New schedule spec
        # Keep other properties the same
        policy=schedule.policy,
        state=schedule.state,
    )

    return ScheduleUpdate(schedule=new_schedule)


async def create_metrics_cleanup_schedule():
    client = await get_temporalio_client()

    system = await SystemSettings.aget_or_create()

    schedule_id = "daily-logs-cleanup"
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            CleanupAppMetricsWorkflow.run,
            id="_",
            task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        ),
        spec=ScheduleSpec(cron_expressions=[system.metrics_cleanup_cron_schedule]),
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
