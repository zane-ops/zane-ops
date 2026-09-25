from datetime import timedelta
import time

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError

from swarm.models import SwarmNode
from temporal.client import TemporalClient
from temporal.shared import SwarmNodeDetails, ProvisionSwarmNodePayload
from temporal.workflows import ProvisionSwarmNodeWorkflow
from zane_api.utils import Colors


class Command(BaseCommand):
    help = (
        "Run the `provision-swarm-node` workflow for a node stored in the "
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
        try:
            main_node = SwarmNode.objects.get(is_initial_install_server=True)
        except SwarmNode.DoesNotExist:  #  SwarmNode.MultipleObjectsReturned
            raise CommandError(f"No main server exists on the cluster")

        new_key = node.ssh_keys.filter(user="root").first()
        if new_key is None:
            raise CommandError(f"No Root SSH key found for the node `{node_id}`")

        main_key = main_node.ssh_keys.filter(user="root").first()
        if main_key is None:
            raise CommandError(f"No Root SSH key found for the main node")

        self.stdout.write(
            f"Using Root SSH key {Colors.ORANGE}{main_key.name}{Colors.ENDC} for MAIN SERVER"
            f" (user={main_key.user})"
        )

        self.stdout.write(
            f"Using Root SSH key {Colors.ORANGE}{new_key.name}{Colors.ENDC} for NEW SERVER"
            f" (user={new_key.user})"
        )

        payload = ProvisionSwarmNodePayload(
            new_node=SwarmNodeDetails(
                id=node.id,
                private_ip=node.private_ip,
                swarm_role=node.swarm_role,  # type: ignore
                cluster_roles=node.cluster_roles,  # type: ignore
                ssh_key=new_key.private_key,
                ssh_port=node.ssh_port,
            ),
            main_node=SwarmNodeDetails(
                id=main_node.id,
                private_ip=main_node.private_ip,
                swarm_role=main_node.swarm_role,  # type: ignore
                cluster_roles=main_node.cluster_roles,  # type: ignore
                ssh_key=main_key.private_key,
                ssh_port=main_node.ssh_port,
            ),
        )

        workflow_id = f"provision-{node.id}-{int(time.time())}"
        self.stdout.write(
            f"Provisioning {Colors.ORANGE}{payload.new_node.private_ip}:{payload.new_node.ssh_port}{Colors.ENDC}"
            f" as a {Colors.ORANGE}{payload.new_node.swarm_role}{Colors.ENDC}..."
        )

        result = async_to_sync(self.run_workflow)(payload, workflow_id)
        self.stdout.write(f"{Colors.GREEN}Workflow finished ✅{Colors.ENDC} {result=}")

    async def run_workflow(self, payload: ProvisionSwarmNodePayload, workflow_id: str):
        handle = await TemporalClient.astart_workflow(
            ProvisionSwarmNodeWorkflow.run,
            payload,
            id=workflow_id,
        )
        self.stdout.write(
            f"Started workflow `{workflow_id}`, waiting for the result..."
        )
        return await handle.result(rpc_timeout=timedelta(seconds=30))
