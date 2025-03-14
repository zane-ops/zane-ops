from typing import Any, Awaitable, Callable, Union, Optional

import logging

from django.conf import settings
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

# Get the logger for this module
logger = logging.getLogger(__name__)


async def get_temporalio_client() -> Client:
    """
    Asynchronously connects to the Temporal server and returns a Temporal client.
    """
    try:
        return await Client.connect(
            settings.TEMPORALIO_SERVER_URL, namespace="default"
        )
    except Exception as e:
        logger.error(f"Failed to connect to Temporal server: {e}")
        raise


async def start_workflow(
    workflow: Union[str, Callable[..., Awaitable[Any]]],
    args: list[Any],  # Enforce args as a list,
    id: str,
    task_queue: str = "main-task-queue",
    retry_policy: Optional[RetryPolicy] = RetryPolicy(
        maximum_attempts=2,
    ),
) -> WorkflowHandle:
    """
    Asynchronously starts a Temporal workflow.

    Args:
        workflow: The workflow to start (either a function or a string identifier).
        args: The arguments to pass to the workflow (must be a list).
        id: The unique identifier for the workflow.
        task_queue: The task queue to use for the workflow.
        retry_policy: The retry policy to use for the workflow.

    Returns:
        A WorkflowHandle for the started workflow.
    """
    client = await get_temporalio_client()
    try:
        await client.start_workflow(
            workflow,
            *args,  # Unpack the args here
            id=id,
            task_queue=task_queue,
            retry_policy=retry_policy,
        )
        logger.info(f"Started workflow {workflow} with ID {id}")
    except WorkflowAlreadyStartedError:
        logger.warning(f"Workflow with ID {id} already started.")
        pass  # Handle gracefully: don't raise an exception
    except Exception as e:
        logger.error(f"Failed to start workflow {workflow} with ID {id}: {e}")
        raise  # Re-raise the exception after logging

    return await client.get_workflow_handle(id)
