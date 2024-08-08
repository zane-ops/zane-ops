from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import acreate_project_resources
    from .shared import CreateProjectResourcesPayload


@workflow.defn(name="create-project-resources-workflow")
class CreateProjectResourcesWorkflow:
    @workflow.run
    async def run(self, payload: CreateProjectResourcesPayload) -> dict:
        retry_policy = RetryPolicy(maximum_attempts=5)
        await workflow.execute_activity(
            acreate_project_resources,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=retry_policy,
        )

