from datetime import timedelta
import time

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError

from swarm.models import SwarmNode
from temporal.client import TemporalClient
from temporal.shared import DrainSwarmNodePayload
from temporal.workflows import DetachSwarmNodeFromClusterWorkflow
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
            node = SwarmNode.objects.get(id=node_id)
        except SwarmNode.DoesNotExist:
            raise CommandError(f"A server with the id `{node_id}` does not exist")

        if node.is_initial_install_server:
            raise CommandError(f"Cannot detach the main server from the cluster")

        if node.swarm_node_id is None:
            raise CommandError(
                f"The node `{node_id}` is not part of the swarm cluster (no swarm node id)"
            )

        payload = DrainSwarmNodePayload(
            id=node.id,
            swarm_node_id=node.swarm_node_id,
            swarm_role=node.swarm_role,  # type: ignore
        )

        workflow_id = f"detach-{node.id}-{int(time.time())}"
        self.stdout.write(
            f"Detaching {Colors.ORANGE}{node.private_ip}{Colors.ENDC}"
            f" (swarm node {Colors.ORANGE}{payload.swarm_node_id}{Colors.ENDC}) from the cluster..."
        )

        result = async_to_sync(self.run_workflow)(payload, workflow_id)
        self.stdout.write(f"{Colors.GREEN}Workflow finished ✅{Colors.ENDC} {result=}")

    async def run_workflow(self, payload: DrainSwarmNodePayload, workflow_id: str):
        handle = await TemporalClient.astart_workflow(
            DetachSwarmNodeFromClusterWorkflow.run,
            payload,
            id=workflow_id,
        )
        self.stdout.write(
            f"Started workflow `{workflow_id}`, waiting for the result..."
        )
        return await handle.result(rpc_timeout=timedelta(seconds=30))
