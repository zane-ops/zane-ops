from datetime import timedelta
import time

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError

from swarm.models import SwarmNode
from temporal.client import TemporalClient
from temporal.shared import ClusterSwarmNodePair, ClusterSwarmNodeDetails
from temporal.workflows import RemoveSwarmNodeFromClusterWorkflow
from zane_api.utils import Colors


class Command(BaseCommand):
    help = (
        "Run the `detach-swarm-node-from-cluster` workflow for a node stored in the "
        "database, on the main task queue. The `temporal-main-worker` process "
        "needs to be running."
    )

    def add_arguments(self, parser):
        parser.add_argument("node", help="id of the swarm node, ex: node_xxxxxxxx")

    def handle(self, *args, **options):
        node_id: str = options["node"]

        try:
            target_node = SwarmNode.objects.get(id=node_id)
        except SwarmNode.DoesNotExist:
            raise CommandError(f"A server with the id `{node_id}` does not exist")

        if target_node.is_initial_install_server:
            raise CommandError(f"Cannot detach the main server from the cluster")

        if target_node.swarm_node_id is None:
            raise CommandError(
                f"The node `{node_id}` is not part of the swarm cluster (no swarm node id)"
            )

        try:
            main_node = SwarmNode.objects.get(is_initial_install_server=True)
        except SwarmNode.DoesNotExist:
            raise CommandError(f"No main server exists on the cluster")

        if main_node.swarm_node_id is None:
            raise CommandError(f"The main node has no swarm node id")

        target_key = target_node.ssh_keys.filter(user="root").first()
        if target_key is None:
            raise CommandError(f"No Root SSH key found for the node `{node_id}`")

        main_key = main_node.ssh_keys.filter(user="root").first()
        if main_key is None:
            raise CommandError(f"No Root SSH key found for the main node")

        self.stdout.write(
            f"Using Root SSH key {Colors.ORANGE}{main_key.name}{Colors.ENDC} for MAIN SERVER"
            f" (user={main_key.user})"
        )

        self.stdout.write(
            f"Using Root SSH key {Colors.ORANGE}{target_key.name}{Colors.ENDC} for TARGET SERVER"
            f" (user={target_key.user})"
        )

        payload = ClusterSwarmNodePair(
            target_node=ClusterSwarmNodeDetails(
                id=target_node.id,
                private_ip=target_node.private_ip,
                swarm_role=target_node.swarm_role,  # type: ignore
                cluster_roles=target_node.cluster_roles,  # type: ignore
                ssh_key=target_key.private_key,
                ssh_port=target_node.ssh_port,
                swarm_node_id=target_node.swarm_node_id,
            ),
            main_node=ClusterSwarmNodeDetails(
                id=main_node.id,
                private_ip=main_node.private_ip,
                swarm_role=main_node.swarm_role,  # type: ignore
                cluster_roles=main_node.cluster_roles,  # type: ignore
                ssh_key=main_key.private_key,
                ssh_port=main_node.ssh_port,
                swarm_node_id=main_node.swarm_node_id,
            ),
        )

        workflow_id = f"detach-{target_node.id}-{int(time.time())}"
        self.stdout.write(
            f"Detaching {Colors.ORANGE}{target_node.private_ip}{Colors.ENDC}"
            f" (swarm node {Colors.ORANGE}{target_node.swarm_node_id}{Colors.ENDC}) from the cluster..."
        )

        result = async_to_sync(self.run_workflow)(payload, workflow_id)
        self.stdout.write(f"{Colors.GREEN}Workflow finished ✅{Colors.ENDC} {result=}")

    async def run_workflow(self, payload: ClusterSwarmNodePair, workflow_id: str):
        handle = await TemporalClient.astart_workflow(
            RemoveSwarmNodeFromClusterWorkflow.run,
            payload,
            id=workflow_id,
        )
        self.stdout.write(
            f"Started workflow `{workflow_id}`, waiting for the result..."
        )
        return await handle.result(rpc_timeout=timedelta(seconds=30))
