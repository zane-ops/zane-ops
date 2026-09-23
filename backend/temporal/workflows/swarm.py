import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy


from temporalio.exceptions import ActivityError, is_cancelled_exception
from temporalio.workflow import ActivityHandle

with workflow.unsafe.imports_passed_through():
    from ..activities import ComposeStackActivities
    from ..schedules import MonitorComposeStackActivites
    from ..shared import SwarmNodeDetails
    from swarm.models import SwarmNode


@workflow.defn(name="provision-swarm-node")
class ProvisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, deployment: SwarmNodeDetails):
        print(f"Running workflow ProvisionSwarmNodeWorkflow.run({deployment=})")
        pass
