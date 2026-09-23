from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import SwarmNodeActivities
    from ..shared import SwarmNodeDetails


@workflow.defn(name="provision-swarm-node")
class ProvisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, node: SwarmNodeDetails) -> str:
        print(f"Running workflow ProvisionSwarmNodeWorkflow.run({node.private_ip=})")
        result = await workflow.execute_activity_method(
            SwarmNodeActivities.create_ssh_key_temp_file,
            node,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        res = await workflow.execute_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            SwarmNodeActivities.delete_ssh_key_temp_file,
            result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )
        return res
