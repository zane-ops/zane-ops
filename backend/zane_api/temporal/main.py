from typing import Any, Awaitable, Callable, Union

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from django.conf import settings
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


async def get_temporalio_client():
    return await Client.connect(settings.TEMPORALIO_SERVER_URL, namespace="default")


def trigger_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: Any,
    id: str,
    task_queue="main-task-queue",
    retry_policy=RetryPolicy(
        maximum_attempts=2,
    ),
):
    async def _trigger():
        print("start_workflow()")
        client = await get_temporalio_client()
        try:
            await client.start_workflow(
                workflow,
                args,
                id=id,
                task_queue=task_queue,
                retry_policy=retry_policy,
            )
        except WorkflowAlreadyStartedError:
            pass

        return await client.get_workflow_handle(id)

    return _trigger


async def start_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: Any,
    id: str,
    task_queue="main-task-queue",
    retry_policy=RetryPolicy(
        maximum_attempts=2,
    ),
) -> WorkflowHandle:
    print("start_workflow()")
    client = await get_temporalio_client()
    try:
        await client.start_workflow(
            workflow,
            args,
            id=id,
            task_queue=task_queue,
            retry_policy=retry_policy,
        )
    except WorkflowAlreadyStartedError:
        pass

    return await client.get_workflow_handle(id)
