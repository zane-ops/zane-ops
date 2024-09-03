from datetime import timedelta
from typing import Any, Awaitable, Callable, Union

import temporalio.common
from temporalio import workflow
from temporalio.service import RPCError

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


async def pause_schedule(id: str, note: str = None):
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )

    await handle.pause(note=note)


async def unpause_schedule(id: str, note: str = None):
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )

    await handle.unpause(note=note)


async def delete_schedule(id: str):
    client = await get_temporalio_client()
    handle = client.get_schedule_handle(
        f"schedule-{id}",
    )
    await handle.delete()


@async_to_sync
async def start_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    arg: Any,
    id: str,
    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
    execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    retry_policy=RetryPolicy(
        maximum_attempts=1,
    ),
) -> WorkflowHandle:
    client = await get_temporalio_client()
    try:
        await client.start_workflow(
            workflow=workflow,
            arg=arg,
            id=id,
            task_queue=task_queue,
            retry_policy=retry_policy,
            execution_timeout=execution_timeout,
        )
    except WorkflowAlreadyStartedError:
        pass

    return client.get_workflow_handle(id)


@async_to_sync
async def workflow_signal(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    workflow_id: str,
    signal: Union[str, Callable[..., Awaitable[Any]]],
    arg: Any = temporalio.common._arg_unset,
    timeout: timedelta = timedelta(seconds=5),
):
    client = await get_temporalio_client()
    workflow_handle = client.get_workflow_handle_for(
        workflow=workflow, workflow_id=workflow_id
    )
    try:
        await workflow_handle.signal(
            signal,
            arg=arg,
            rpc_timeout=timeout,
        )
    except RPCError:
        # probably because the signal sent to the workflow could not be executed
        pass
