import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import greet, say_goodbye, get_project
    from .shared import HelloPayload, DeployPayload


@workflow.defn(name="hello-workflow")
class HelloWorkflow:
    @workflow.run
    async def run(self, payload: HelloPayload) -> str:
        hello = await workflow.execute_activity(
            greet,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
        )

        await asyncio.sleep(60)
        workflow.logger.info("Sleeping for 60 seconds")

        bye = await workflow.execute_activity(
            say_goodbye,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
        )

        return f"{hello}, {bye}"


@workflow.defn(name="get-project-workflow")
class GetProjectWorkflow:
    def __init__(self) -> None:
        self._project = None

    @workflow.query
    def project(self) -> dict | None:
        return self._project

    @workflow.run
    async def run(self, payload: DeployPayload) -> dict:
        retry_policy = RetryPolicy(maximum_attempts=5)
        self._project = await workflow.execute_activity(
            get_project,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

        return self._project


async def main():
    print(f"running main()...")
    from django.conf import settings

    print(f"{settings=}")
    client: Client = await Client.connect("localhost:7233", namespace="default")
    print(f"Client: {client=}")
    data = HelloPayload(name="coocoo")
    print(f"payload: {data=}")
    handle = await client.start_workflow(
        HelloWorkflow.run,
        data,
        id=f"hello-{data.name}",
        task_queue="main-task-queue",
    )
    print(f"Handle: {handle=}")


if __name__ == "__main__":
    asyncio.run(main())
