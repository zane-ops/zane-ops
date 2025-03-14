import asyncio
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from ...temporal import get_temporalio_client
from ...temporal import CleanupAppLogsWorkflow
from ...utils import Colors
from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleUpdateInput,
    ScheduleUpdate,
)
from temporalio.service import RPCError

# Get the logger for this module
logger = logging.getLogger(__name__)


async def update_schedule_simple(input: ScheduleUpdateInput) -> ScheduleUpdate:
    """
    Updates the schedule with a simple cron expression.

    Args:
        input: ScheduleUpdateInput containing the existing schedule.

    Returns:
        ScheduleUpdate object with the updated schedule.
    """
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


async def create_metrics_cleanup_schedule() -> None:
    """
    Creates or updates a schedule for daily cleanup of application logs using Temporal.
    """
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
        logger.info(f"Successfully updated schedule: {schedule_id}")
    except RPCError:
        # probably because the schedule doesn't exist
        logger.warning(
            f"Schedule {schedule_id} does not exist. Attempting to create it."
        )
        try:
            await client.create_schedule(
                schedule_id,
                schedule,
                rpc_timeout=timedelta(seconds=5),
            )
            logger.info(f"Successfully created schedule: {schedule_id}")
        except Exception as e:
            logger.exception(f"Failed to create schedule {schedule_id}: {e}")
    except Exception as e:
        logger.exception(f"Failed to update schedule {schedule_id}: {e}")


class Command(BaseCommand):
    help = "Create log cleanup schedule"

    def handle(self, *args, **options) -> None:
        """
        Handles the command execution by running the asynchronous schedule creation function.
        """
        try:
            asyncio.run(create_metrics_cleanup_schedule())
            self.stdout.write(
                self.style.SUCCESS("Successfully created/updated log cleanup schedule.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to create/update log cleanup schedule: {e}")
            )
            logger.error(f"Failed to create/update log cleanup schedule: {e}")
