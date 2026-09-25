import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import SwarmNodeActivities
    from ..shared import (
        ProvisionSwarmNodePayload,
        DockerInstallContext,
        ProvisionSwarmNodeContext,
        ProvisionSwarmNodeContextWithRole,
        DockerSwarmJoinContext,
        DockerNodeUpdateContext,
        SwarmNodeStatusResult,
    )
    from zane_api.utils import Colors


@workflow.defn(name="provision-swarm-node")
class ProvisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: ProvisionSwarmNodePayload):
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        print(
            f"Running workflow ProvisionSwarmNodeWorkflow.run({payload.main_node.private_ip=}, {payload.new_node.private_ip=})"
        )
        print(
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        tmp_dir = await workflow.execute_activity_method(
            SwarmNodeActivities.prepare_node_deployment,
            payload.new_node,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        node_deployment_result = SwarmNodeStatusResult(
            node=payload.new_node,
            status="FAILED",
        )

        tmp_dir = await workflow.execute_activity_method(
            SwarmNodeActivities.create_ssh_keys_temp_dir,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        ssh_test_new_task = workflow.start_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            ProvisionSwarmNodeContext(node=payload.new_node, tmp_dir=tmp_dir),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        ssh_test_main_task = workflow.start_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            ProvisionSwarmNodeContext(node=payload.main_node, tmp_dir=tmp_dir),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        result = await asyncio.gather(ssh_test_new_task, ssh_test_main_task)

        if all(result):
            docker_info = await workflow.execute_activity_method(
                SwarmNodeActivities.check_docker_installation,
                ProvisionSwarmNodeContext(node=payload.new_node, tmp_dir=tmp_dir),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            docker_info = await workflow.execute_activity_method(
                SwarmNodeActivities.install_latest_docker_version,
                DockerInstallContext(
                    node=payload.new_node, tmp_dir=tmp_dir, info=docker_info
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            node_deployment_result.docker_info = docker_info

            if docker_info is not None:
                credentials = await workflow.execute_activity_method(
                    SwarmNodeActivities.get_swarm_join_token,
                    ProvisionSwarmNodeContextWithRole(
                        node=payload.main_node,
                        tmp_dir=tmp_dir,
                        swarm_role=payload.new_node.swarm_role,
                    ),
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                )

                if credentials is not None:
                    swarm_info = await workflow.execute_activity_method(
                        SwarmNodeActivities.join_swarm_cluster,
                        DockerSwarmJoinContext(
                            node=payload.new_node,
                            tmp_dir=tmp_dir,
                            credentials=credentials,
                            info=docker_info,
                        ),
                        start_to_close_timeout=timedelta(minutes=3),
                        retry_policy=self.retry_policy,
                    )

                    if swarm_info:
                        node_deployment_result.swarm_hostname = (
                            await workflow.execute_activity_method(
                                SwarmNodeActivities.update_node_labels,
                                DockerNodeUpdateContext(
                                    node=payload.new_node,
                                    tmp_dir=tmp_dir,
                                    swarm_info=swarm_info,
                                ),
                                start_to_close_timeout=timedelta(minutes=3),
                                retry_policy=self.retry_policy,
                            )
                        )

        await workflow.execute_activity_method(
            SwarmNodeActivities.delete_ssh_keys_temp_dir,
            tmp_dir,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            SwarmNodeActivities.finish_and_save_node_deployment,
            node_deployment_result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        print(
            f"\n{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        print(
            f" DONE Running workflow ProvisionSwarmNodeWorkflow.run({payload.main_node.private_ip=}, {payload.new_node.private_ip=})"
        )
        print(
            f"{Colors.BLUE}==============================================================={Colors.ENDC}\n\n"
        )
        return
