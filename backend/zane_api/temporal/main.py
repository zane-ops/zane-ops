from typing import Any, Awaitable, Callable, Union

from django.conf import settings
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


async def get_temporalio_client():
    return await Client.connect(settings.TEMPORALIO_SERVER_URL, namespace="default")


async def start_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: Any,
    id: str,
    task_queue="main-task-queue",
    retry_policy=RetryPolicy(
        maximum_attempts=2,
    ),
) -> WorkflowHandle:
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
