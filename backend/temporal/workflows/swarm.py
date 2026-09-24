from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import SwarmNodeActivities
    from ..shared import ProvisionSwarmNodePayload, DockerSystemInfo
    from zane_api.utils import Colors


@workflow.defn(name="provision-swarm-node")
class ProvisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, details: ProvisionSwarmNodePayload) -> DockerSystemInfo | None:
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        print(
            f"Running workflow ProvisionSwarmNodeWorkflow.run({details.main_node.private_ip=}, {details.new_node.private_ip=})"
        )
        print(
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        result = await workflow.execute_activity_method(
            SwarmNodeActivities.create_ssh_keys_temp_dir,
            details,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        res = await workflow.execute_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        docker_info = await workflow.execute_activity_method(
            SwarmNodeActivities.check_docker_installation,
            result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            SwarmNodeActivities.delete_ssh_keys_temp_dir,
            result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )
        print(
            f"\n{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        print(
            f" DONE Running workflow ProvisionSwarmNodeWorkflow.run({details.main_node.private_ip=}, {details.new_node.private_ip=})"
        )
        print(
            f"{Colors.BLUE}==============================================================={Colors.ENDC}\n\n"
        )
        return docker_info
