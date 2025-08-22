from datetime import timedelta
from typing import Any, Awaitable, Callable, Optional, Union

import temporalio.common
from temporalio import workflow
from temporalio.service import RPCError


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
from temporalio.types import (
    MethodAsyncNoParam,
    MethodAsyncSingleParam,
    ReturnType,
    SelfType,
)

with workflow.unsafe.imports_passed_through():
    from asgiref.sync import async_to_sync
    from django.conf import settings


async def get_temporalio_client():
    return await Client.connect(
        settings.TEMPORALIO_SERVER_URL, namespace=settings.TEMPORALIO_WORKER_NAMESPACE
    )


class TemporalClient:
    _client: Optional[Client] = None

    @classmethod
    async def _ensure_client(cls):
        if cls._client is None:
            cls._client = await get_temporalio_client()
        return cls._client

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
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
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
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
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
    async def adelete_schedule(cls, id: str):
        client = await cls._ensure_client()
        handle = client.get_schedule_handle(f"schedule-{id}")
        await handle.delete()
