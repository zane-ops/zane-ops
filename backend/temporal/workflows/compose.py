import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import (
        DockerSwarmActivities,
        GitActivities,
    )
    from ..shared import ComposeStackDeploymentDetails


@workflow.defn(name="deploy-compose-stack")
class DeployComposeStackWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: ComposeStackDeploymentDetails):
        pass
