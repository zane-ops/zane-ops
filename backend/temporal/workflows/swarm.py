import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import (
    ActivityError,
    is_cancelled_exception,
)
from temporalio.workflow import ActivityHandle, ActivityCancellationType

with workflow.unsafe.imports_passed_through():
    from ..activities import SwarmNodeActivities
    from zane_api.utils import Colors

from ..shared import (
    SwarmNodePair,
    ClusterSwarmNodePair,
    DockerInstallContext,
    SwarmNodeSSHContext,
    SwarmNodePairSSHContext,
    GetSwarmJoinTokenInput,
    DockerSwarmJoinContext,
    DockerNodeUpdateContext,
    SwarmNodeStatusResult,
    DockerNodeHealthCheckContext,
)


@workflow.defn(name="provision-swarm-node")
class ProvisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )
        self.cancellation_requested = False

    @workflow.signal
    async def cancel(self):
        self.cancellation_requested = True
        print(f"Received signal {self.cancellation_requested=}")

    async def monitor_cancellation(
        self,
        activity_handle: ActivityHandle,
        timeout: Optional[timedelta] = None,
    ):
        """
        Monitors an activity for cancellation requests. If a cancellation is requested,
        cancels the activity handle.

        Args:
            activity_handle: The activity handle to monitor and potentially cancel
            node_id: The id of the node being provisioned
            timeout: How long to wait for a cancellation signal, `None` to wait until the monitor is cancelled
        """
        try:
            print(f"await monitor_cancellation({activity_handle.get_name()})")
            await workflow.wait_condition(
                lambda: self.cancellation_requested,
                timeout=timeout,
            )
            print(f"cancelling activity {activity_handle.get_name()}")
        except (asyncio.CancelledError, TimeoutError):
            pass  # do nothing
        else:
            activity_handle.cancel()

    async def run_cancellable[T](self, activity_handle: ActivityHandle[T]) -> T:
        """
        Await the activity, cancelling it if a cancellation is requested for `node_id`.
        The activity must send heartbeats (and have a `heartbeat_timeout`) for the cancellation to reach it:
        https://docs.temporal.io/develop/python/cancellation#cancel-activity

        The activity should also use `cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED`,
        so that its cleanup (which may need the SSH keys) finishes before the workflow's `finally` block deletes them.
        """
        monitor_task = asyncio.create_task(self.monitor_cancellation(activity_handle))
        try:
            return await activity_handle
        finally:
            monitor_task.cancel()

    @workflow.run
    async def run(self, payload: SwarmNodePair) -> SwarmNodeStatusResult:
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"Running workflow ProvisionSwarmNodeWorkflow.run({payload.main_node.private_ip=}, {payload.target_node.private_ip=})\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )

        status = await workflow.execute_activity_method(
            SwarmNodeActivities.prepare_node_deployment,
            payload.target_node,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )

        tmp_dir: str | None = None
        node_deployment_result = SwarmNodeStatusResult(
            id=payload.target_node.id,
            status=status,
        )
        try:
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
                heartbeat_timeout=timedelta(seconds=3),
                cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            )

            ssh_test_main_task = workflow.start_activity_method(
                SwarmNodeActivities.test_ssh_connection,
                SwarmNodeSSHContext(
                    node=payload.main_node,
                    tmp_dir=tmp_dir,
                    target_node=payload.target_node,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
                heartbeat_timeout=timedelta(seconds=3),
                cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            )

            await asyncio.gather(
                self.run_cancellable(ssh_test_new_task),
                self.run_cancellable(ssh_test_main_task),
            )

            system_info = await self.run_cancellable(
                workflow.start_activity_method(
                    SwarmNodeActivities.check_os_and_arch_compatibility,
                    SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                    heartbeat_timeout=timedelta(seconds=3),
                    cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                ),
            )
            node_deployment_result.architecture = system_info.architecture

            docker_check_new_task = workflow.start_activity_method(
                SwarmNodeActivities.check_docker_installation,
                SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
                heartbeat_timeout=timedelta(seconds=3),
                cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            )

            docker_check_main_task = workflow.start_activity_method(
                SwarmNodeActivities.get_main_node_docker_info,
                payload,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            docker_info, main_docker_info = await asyncio.gather(
                self.run_cancellable(docker_check_new_task),
                docker_check_main_task,
            )

            docker_info = await self.run_cancellable(
                workflow.start_activity_method(
                    SwarmNodeActivities.install_docker_on_node,
                    DockerInstallContext(
                        node=payload.target_node,
                        tmp_dir=tmp_dir,
                        info=docker_info,
                        version_to_install=main_docker_info.ServerVersion,
                    ),
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                    heartbeat_timeout=timedelta(seconds=3),
                    cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                ),
            )

            node_deployment_result.docker_info = docker_info

            await self.run_cancellable(
                workflow.start_activity_method(
                    SwarmNodeActivities.check_swarm_ports_reachability,
                    SwarmNodePairSSHContext(pair=payload, tmp_dir=tmp_dir),
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=self.retry_policy,
                    heartbeat_timeout=timedelta(seconds=3),
                    cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                ),
            )

            credentials = await self.run_cancellable(
                workflow.start_activity_method(
                    SwarmNodeActivities.get_swarm_join_token,
                    GetSwarmJoinTokenInput(
                        tmp_dir=tmp_dir,
                        swarm_role=payload.target_node.swarm_role,
                        node=payload.main_node,
                        target_node=payload.target_node,
                    ),
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                    heartbeat_timeout=timedelta(seconds=3),
                    cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                ),
            )

            swarm_info = await self.run_cancellable(
                workflow.start_activity_method(
                    SwarmNodeActivities.join_swarm_cluster,
                    DockerSwarmJoinContext(
                        node=payload.target_node,
                        tmp_dir=tmp_dir,
                        credentials=credentials,
                        info=docker_info,
                    ),
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=self.retry_policy,
                    heartbeat_timeout=timedelta(seconds=3),
                    cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                ),
            )

            node_deployment_result.docker_info.Swarm = swarm_info

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

            healthcheck_result = await workflow.execute_activity_method(
                SwarmNodeActivities.run_swarm_node_services_healthcheck,
                DockerNodeHealthCheckContext(
                    node=payload.target_node,
                    swarm_info=swarm_info,
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=self.retry_policy,
            )

            all_healthy = all(
                [
                    service.status == "running"
                    for _, service in healthcheck_result.services.items()
                ]
            )

            node_deployment_result.status = "ACTIVE" if all_healthy else "PROVISIONING"
            node_deployment_result.services = healthcheck_result.services

        except ActivityError as e:
            print(f"ActivityError({e=}) !")
            reason = str(e.cause)
            if is_cancelled_exception(e):
                reason = "Provision server workflow was manually cancelled ❌"

            node_deployment_result.status = "FAILED"
            node_deployment_result.status_message = reason
        except Exception as e:
            reason = str(e)
            node_deployment_result.status = "FAILED"
            node_deployment_result.status_message = f"Unknown Error: {reason}"
        finally:
            if tmp_dir is not None:
                await workflow.execute_activity_method(
                    SwarmNodeActivities.delete_ssh_keys_temp_dir,
                    SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

            await workflow.execute_activity_method(
                SwarmNodeActivities.finish_and_save_node_provisioning,
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


@workflow.defn(name="deprovision-swarm-node")
class DeprovisionSwarmNodeWorkflow:
    def __init__(self):
        self.retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )

    @workflow.run
    async def run(self, payload: ClusterSwarmNodePair) -> SwarmNodeStatusResult:
        print(
            f"\n\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
            f"Running workflow DeprovisionSwarmNodeWorkflow.run({payload.target_node.id=}, {payload.target_node.private_ip=})\n"
            f"{Colors.BLUE}==============================================================={Colors.ENDC}"
        )
        # Not in the `try` block, if the node cannot be deprovisioned we don't want to touch it
        current_status = await workflow.execute_activity_method(
            SwarmNodeActivities.prepare_node_deprovision,
            payload.target_node,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=self.retry_policy,
        )
        node_deployment_result = SwarmNodeStatusResult(
            id=payload.target_node.id,
            status=current_status,
        )
        tmp_dir: str | None = None

        try:
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
                SwarmNodeSSHContext(
                    node=payload.main_node,
                    tmp_dir=tmp_dir,
                    target_node=payload.target_node,
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            await asyncio.gather(ssh_test_target_task, ssh_test_main_task)

            drain_result = await workflow.execute_activity_method(
                SwarmNodeActivities.drain_swarm_node_and_remove_labels,
                payload,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=self.retry_policy,
            )

            if drain_result == "NOT_IN_SWARM":
                # The node is already out of the swarm, nothing left to drain or remove
                node_deployment_result.status = "REMOVED"
                node_deployment_result.status_message = "The node was not found in the swarm, it may have been removed manually"
            else:
                node_deployment_result.status = "DOWN"

                all_drained = await workflow.execute_activity_method(
                    SwarmNodeActivities.wait_for_global_services_to_be_drained,
                    payload,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=self.retry_policy,
                )
                if all_drained:
                    node_deployment_result.status = "DRAINED"

                await workflow.execute_activity_method(
                    SwarmNodeActivities.detach_swarm_node_from_cluster,
                    SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

                await workflow.execute_activity_method(
                    SwarmNodeActivities.remove_swarm_node_from_cluster,
                    payload,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )
                node_deployment_result.status = "REMOVED"

        except ActivityError as e:
            print(f"ActivityError({e=}) !")
            reason = str(e.cause)
            if is_cancelled_exception(e):
                reason = "Deprovision server workflow was manually cancelled ❌"

            # We keep the last status reached, as the node might still be part of the cluster
            node_deployment_result.status_message = reason
        finally:
            if tmp_dir is not None:
                await workflow.execute_activity_method(
                    SwarmNodeActivities.delete_ssh_keys_temp_dir,
                    SwarmNodeSSHContext(node=payload.target_node, tmp_dir=tmp_dir),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=self.retry_policy,
                )

            await workflow.execute_activity_method(
                SwarmNodeActivities.finish_and_save_node_deprovisioning,
                node_deployment_result,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )

            print(
                f"\n{Colors.BLUE}==============================================================={Colors.ENDC}\n"
                f" DONE Running workflow DeprovisionSwarmNodeWorkflow.run({payload.target_node.id=}, {payload.target_node.private_ip=})\n"
                f"{Colors.BLUE}==============================================================={Colors.ENDC}\n\n"
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
