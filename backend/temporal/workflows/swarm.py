import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from ..activities import SwarmNodeActivities
    from zane_api.utils import Colors

from ..shared import (
    SwarmNodePair,
    ClusterSwarmNodePair,
    RemoveSwarmNodeContext,
    DockerInstallContext,
    SwarmNodeSSHContext,
    GetSwarmJoinTokenInput,
    DockerSwarmJoinContext,
    DockerNodeUpdateContext,
    SwarmNodeStatusResult,
)


@workflow.defn(name="provision-swarm-node")
class ProvisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: SwarmNodePair) -> SwarmNodeStatusResult:
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"Running workflow ProvisionSwarmNodeWorkflow.run({payload.main_node.private_ip=}, {payload.target_node.private_ip=})\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        await workflow.execute_activity_method(
            SwarmNodeActivities.prepare_node_deployment,
            payload.target_node,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        node_deployment_result = SwarmNodeStatusResult(
            id=payload.target_node.id,
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
            SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        ssh_test_main_task = workflow.start_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            SwarmNodeSSHContext(node=payload.main_node, tmp_dir=tmp_dir),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        result = await asyncio.gather(ssh_test_new_task, ssh_test_main_task)

        if all(result):
            docker_info = await workflow.execute_activity_method(
                SwarmNodeActivities.check_docker_installation,
                SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            docker_info = await workflow.execute_activity_method(
                SwarmNodeActivities.install_latest_docker_version,
                DockerInstallContext(
                    node=payload.target_node, tmp_dir=tmp_dir, info=docker_info
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            node_deployment_result.docker_info = docker_info

            if docker_info is not None:
                credentials = await workflow.execute_activity_method(
                    SwarmNodeActivities.get_swarm_join_token,
                    GetSwarmJoinTokenInput(
                        node=payload.main_node,
                        tmp_dir=tmp_dir,
                        swarm_role=payload.target_node.swarm_role,
                    ),
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                )

                if credentials is not None:
                    swarm_info = await workflow.execute_activity_method(
                        SwarmNodeActivities.join_swarm_cluster,
                        DockerSwarmJoinContext(
                            node=payload.target_node,
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
                                    node=payload.target_node,
                                    tmp_dir=tmp_dir,
                                    swarm_info=swarm_info,
                                ),
                                start_to_close_timeout=timedelta(minutes=3),
                                retry_policy=self.retry_policy,
                            )
                        )

                        if node_deployment_result.swarm_hostname:
                            all_healthy = await workflow.execute_activity_method(
                                SwarmNodeActivities.wait_for_global_services_to_be_propagated,
                                swarm_info,
                                start_to_close_timeout=timedelta(minutes=5),
                                retry_policy=self.retry_policy,
                            )

                            node_deployment_result.status = (
                                "ACTIVE" if all_healthy else "PROVISIONING"
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
            f"\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f" DONE Running workflow ProvisionSwarmNodeWorkflow.run({payload.main_node.private_ip=}, {payload.target_node.private_ip=})\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}\n\n"
        )
        return node_deployment_result


@workflow.defn(name="remove-swarm-node-from-cluster")
class RemoveSwarmNodeFromClusterWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: ClusterSwarmNodePair) -> SwarmNodeStatusResult:
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"Running workflow RemoveSwarmNodeFromClusterWorkflow.run({payload.target_node.id=}, {payload.target_node.private_ip=})\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        node_deployment_result = SwarmNodeStatusResult(
            id=payload.target_node.id,
            status="ACTIVE",
        )

        tmp_dir = await workflow.execute_activity_method(
            SwarmNodeActivities.create_ssh_keys_temp_dir,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        ssh_test_target_task = workflow.start_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        ssh_test_main_task = workflow.start_activity_method(
            SwarmNodeActivities.test_ssh_connection,
            SwarmNodeSSHContext(node=payload.main_node, tmp_dir=tmp_dir),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        result = await asyncio.gather(ssh_test_target_task, ssh_test_main_task)

        if not all(result):
            print("Failed to connect to servers, skipping job")
        else:
            successful = await workflow.execute_activity_method(
                SwarmNodeActivities.drain_swarm_node_and_remove_labels,
                payload,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=self.retry_policy,
            )

            if successful:
                node_deployment_result.status = "DOWN"

                all_removed = await workflow.execute_activity_method(
                    SwarmNodeActivities.wait_for_global_services_to_be_drained,
                    payload,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                )

                if all_removed:
                    node_deployment_result.status = "DRAINED"

                    detached = await workflow.execute_activity_method(
                        SwarmNodeActivities.detach_swarm_node_from_cluster,
                        SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=self.retry_policy,
                    )

                    if detached:
                        removed = await workflow.execute_activity_method(
                            SwarmNodeActivities.remove_swarm_node_from_cluster,
                            RemoveSwarmNodeContext(
                                target_node=payload.target_node,
                                activity_ctx=SwarmNodeSSHContext(
                                    node=payload.main_node, tmp_dir=tmp_dir
                                ),
                            ),
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=self.retry_policy,
                        )

                        if removed:
                            node_deployment_result.status = "REMOVED"

            if node_deployment_result.status == "REMOVED":
                await workflow.execute_activity_method(
                    SwarmNodeActivities.clear_removed_swarm_node_attributes,
                    node_deployment_result,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
            else:
                await workflow.execute_activity_method(
                    SwarmNodeActivities.finish_and_save_node_deployment,
                    node_deployment_result,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

        await workflow.execute_activity_method(
            SwarmNodeActivities.delete_ssh_keys_temp_dir,
            tmp_dir,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"DONE Running workflow RemoveSwarmNodeFromClusterWorkflow.run({payload.target_node.id=}, {payload.target_node.private_ip=})\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        return node_deployment_result


@workflow.defn(name="swarm-healthcheck")
class SwarmHealthcheckWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self):
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"Running workflow SwarmHealthcheckWorkflow.run()\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )

        result = await workflow.execute_activity_method(
            SwarmNodeActivities.run_swarm_healthcheck,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        await workflow.execute_activity_method(
            SwarmNodeActivities.save_swarm_healthcheck,
            result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"DONE Running workflow SwarmHealthcheckWorkflow.run()\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        return result
