from datetime import timedelta
from typing import Any, Awaitable, Callable, Union

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from asgiref.sync import async_to_sync
    from django.conf import settings
from temporalio.client import (
    Client,
    WorkflowHandle,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleIntervalSpec,
)
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


async def get_temporalio_client():
    return await Client.connect(settings.TEMPORALIO_SERVER_URL, namespace="default")


async def create_schedule(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: Any,
    id: str,
    interval: timedelta,
    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
):
    print(f"create_schedule({workflow=}, {id=}, payload={args})")
    client = await get_temporalio_client()
    await client.create_schedule(
        f"schedule-{id}",
        Schedule(
            action=ScheduleActionStartWorkflow(
                workflow=workflow,
                arg=args,
                id=id,
                task_queue=task_queue,
                execution_timeout=execution_timeout,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=interval)]),
        ),
    )


async def pause_schedule(id: str):
    print(f"pause_schedule({id=}")
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )

    await handle.pause()


async def delete_schedule(id: str):
    print(f"delete_schedule({id=}")
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )
    await handle.delete()


@async_to_sync
async def start_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: Any,
    id: str,
    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    retry_policy=RetryPolicy(
        maximum_attempts=1,
    ),
) -> WorkflowHandle:
    print(f"start_workflow({workflow=}, {id=}, payload={args})")
    client = await get_temporalio_client()
    try:
        await client.start_workflow(
            workflow,
            args,
            id=id,
            task_queue=task_queue,
            retry_policy=retry_policy,
            execution_timeout=execution_timeout,
        )
    except WorkflowAlreadyStartedError:
        pass

    return client.get_workflow_handle(id)
