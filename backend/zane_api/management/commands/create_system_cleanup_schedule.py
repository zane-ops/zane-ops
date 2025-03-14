import asyncio
import logging
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
        spec=ScheduleSpec(cron_expressions=["0 */4 * * *"]),  # New schedule spec
        # Keep other properties the same
        policy=schedule.policy,
        state=schedule.state,
    )

    return ScheduleUpdate(schedule=new_schedule)


async def create_system_cleanup_schedule() -> None:
    """
    Creates or updates a schedule for system cleanup using Temporal.
    """
    client = await get_temporalio_client()

    schedule_id = "hourly-system-cleanup"
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
        logger.info(f"Successfully updated system cleanup schedule: {schedule_id}")
    except RPCError:
        # probably because the schedule doesn't exist
        logger.warning(
            f"System cleanup schedule {schedule_id} does not exist. Attempting to create it."
        )
        try:
            await client.create_schedule(
                schedule_id,
                schedule,
                rpc_timeout=timedelta(seconds=5),
            )
            logger.info(f"Successfully created system cleanup schedule: {schedule_id}")
        except Exception as e:
            logger.exception(
                f"Failed to create system cleanup schedule {schedule_id}: {e}"
            )
    except Exception as e:
        logger.exception(
            f"Failed to update system cleanup schedule {schedule_id}: {e}"
        )


class Command(BaseCommand):
    help = "Create system cleanup schedule"

    def handle(self, *args, **options) -> None:
        """
        Handles the command execution by running the asynchronous schedule creation function.
        """
        try:
            asyncio.run(create_system_cleanup_schedule())
            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully created/updated system cleanup schedule."
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to create/update system cleanup schedule: {e}"
                )
            )
            logger.error(f"Failed to create/update system cleanup schedule: {e}")
