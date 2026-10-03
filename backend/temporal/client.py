from datetime import timedelta
import traceback
from typing import Any, Awaitable, Callable, List, Optional, Union

import temporalio.common
from temporalio import workflow
from temporalio.service import RPCError
from dataclasses import dataclass

from temporalio.client import (
    Client,
    WorkflowHandle,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleIntervalSpec,
    ScheduleUpdateInput,
    ScheduleUpdate,
    ScheduleAlreadyRunningError,
)
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.types import (
    MethodAsyncNoParam,
    MethodAsyncSingleParam,
    ReturnType,
    SelfType,
)
from temporalio.api.enums.v1 import EventType


with workflow.unsafe.imports_passed_through():
    from asgiref.sync import async_to_sync
    from django.conf import settings


async def get_temporalio_client():
    return await Client.connect(
        settings.TEMPORALIO_SERVER_URL, namespace=settings.TEMPORALIO_WORKER_NAMESPACE
    )


@dataclass
class StartWorkflowArg:
    workflow: Callable
    payload: Any
    workflow_id: str
    start_delay: Optional[timedelta] = None


@dataclass
class SignalWorkflowArg:
    workflow: Callable
    signal: Callable
    input: Any
    workflow_id: str


class TemporalClient:
    _client: Optional[Client] = None

    @classmethod
    async def _ensure_client(cls):
        if cls._client is None:
            cls._client = await get_temporalio_client()
        return cls._client

    @classmethod
    async def get_workflow_state(cls, id: str):
        """
        Test function to get the WF state
        """
        client = await cls._ensure_client()
        wf = client.get_workflow_handle(id)
        conv = client.data_converter
        scheduled: dict[int, str] = {}

        async for e in wf.fetch_history_events():
            t = e.event_type
            if t == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED:
                a = e.activity_task_scheduled_event_attributes
                scheduled[e.event_id] = a.activity_type.name
                print(
                    "SCHEDULED",
                    a.activity_type.name,
                    await conv.decode(a.input.payloads),
                )
            elif t == EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED:
                a = e.activity_task_completed_event_attributes
                print(
                    "COMPLETED",
                    scheduled[a.scheduled_event_id],
                    await conv.decode(a.result.payloads),
                )
            elif t == EventType.EVENT_TYPE_ACTIVITY_TASK_FAILED:
                a = e.activity_task_failed_event_attributes
                print("FAILED", scheduled[a.scheduled_event_id], a.failure.message)
            elif t == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED:
                a = e.workflow_execution_completed_event_attributes
                print("RESULT", await conv.decode(a.result.payloads))

    @classmethod
    def start_workflow(
        cls,
        workflow: Union[str, Callable[..., Awaitable[Any]]],
        arg: Any,
        id: str,
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
        execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
        retry_policy=RetryPolicy(maximum_attempts=1),
        start_delay: Optional[timedelta] = None,
    ):
        return async_to_sync(cls.astart_workflow)(
            workflow,
            arg,
            id,
            task_queue,
            execution_timeout,
            retry_policy,
            start_delay,
        )

    @classmethod
    async def astart_workflow(
        cls,
        workflow: Union[str, Callable[..., Awaitable[Any]]],
        arg: Any,
        id: str,
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
        execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
        retry_policy=RetryPolicy(maximum_attempts=1),
        start_delay: Optional[timedelta] = None,
    ) -> WorkflowHandle:
        client = await cls._ensure_client()
        try:
            await client.start_workflow(
                workflow=workflow,
                arg=arg,
                id=id,
                task_queue=task_queue,
                retry_policy=retry_policy,
                execution_timeout=execution_timeout,
                start_delay=start_delay,
            )
        except WorkflowAlreadyStartedError as e:
            print(f"{repr(e)} {id=}")
            traceback.print_exc()
        return client.get_workflow_handle(id)

    @classmethod
    def workflow_signal(
        cls,
        workflow: Union[
            MethodAsyncNoParam[SelfType, ReturnType],
            MethodAsyncSingleParam[SelfType, Any, ReturnType],
        ],
        workflow_id: str,
        signal: Union[str, Callable[..., Awaitable[Any]]],
        input: Any = temporalio.common._arg_unset,
        timeout: timedelta = timedelta(seconds=5),
    ):
        return async_to_sync(cls.aworkflow_signal)(
            workflow,
            workflow_id,
            signal,
            input,
            timeout,
        )

    @classmethod
    async def aworkflow_signal(
        cls,
        workflow: Union[
            MethodAsyncNoParam[SelfType, ReturnType],
            MethodAsyncSingleParam[SelfType, Any, ReturnType],
        ],
        workflow_id: str,
        signal: Union[str, Callable[..., Awaitable[Any]]],
        arg: Any = temporalio.common._arg_unset,
        timeout: timedelta = timedelta(seconds=5),
    ):
        client = await cls._ensure_client()
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
            pass

    @classmethod
    def create_schedule(
        cls,
        workflow: Union[str, Callable[..., Awaitable[Any]]],
        args: Any,
        id: str,
        interval: timedelta,
        task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    ):
        return async_to_sync(cls.acreate_schedule)(
            workflow,
            args,
            id,
            interval,
            task_queue,
            execution_timeout,
        )

    @classmethod
    async def acreate_schedule(
        cls,
        workflow: Union[str, Callable[..., Awaitable[Any]]],
        args: Any,
        id: str,
        interval: timedelta,
        task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
        execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
    ):
        client = await cls._ensure_client()
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

    @classmethod
    async def create_or_update_schedule(
        cls,
        schedule_id: str,
        workflow: Callable[..., Awaitable[Any]],
        schedule_cron: str,
        task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
    ):
        client = await cls._ensure_client()

        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                workflow, id=f"{schedule_id}-workflow", task_queue=task_queue
            ),
            spec=ScheduleSpec(cron_expressions=[schedule_cron]),
        )

        handle = client.get_schedule_handle(schedule_id)

        def update_schedule_simple(input: ScheduleUpdateInput):
            schedule = input.description.schedule

            # Update the schedule
            new_schedule = Schedule(
                spec=ScheduleSpec(cron_expressions=[schedule_cron]),
                action=ScheduleActionStartWorkflow(
                    workflow, id=f"{schedule_id}-workflow", task_queue=task_queue
                ),
                # Keep other properties the same
                policy=schedule.policy,
                state=schedule.state,
            )

            return ScheduleUpdate(schedule=new_schedule)

        try:
            await handle.update(
                update_schedule_simple, rpc_timeout=timedelta(seconds=5)
            )
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

    @classmethod
    def pause_schedule(cls, id: str, note: Optional[str] = None):
        return async_to_sync(cls.apause_schedule)(id, note)

    @classmethod
    async def apause_schedule(cls, id: str, note: Optional[str] = None):
        client = await cls._ensure_client()
        handle = client.get_schedule_handle(f"schedule-{id}")
        await handle.pause(note=note)

    @classmethod
    def unpause_schedule(cls, id: str, note: Optional[str] = None):
        return async_to_sync(cls.aunpause_schedule)(id, note)

    @classmethod
    async def aunpause_schedule(cls, id: str, note: Optional[str] = None):
        client = await cls._ensure_client()
        handle = client.get_schedule_handle(f"schedule-{id}")
        await handle.unpause(note=note)

    @classmethod
    def delete_schedule(cls, id: str):
        return async_to_sync(cls.adelete_schedule)(id)

    @classmethod
    async def adelete_schedule(cls, id: str, prefix: str | None = "schedule-"):
        client = await cls._ensure_client()
        schedule_id = id if prefix is None else f"{prefix}{id}"
        handle = client.get_schedule_handle(schedule_id)
        await handle.delete()
