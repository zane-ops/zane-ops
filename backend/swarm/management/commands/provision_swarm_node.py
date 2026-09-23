from datetime import timedelta
import time

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError

from swarm.models import SwarmNode
from temporal.client import TemporalClient
from temporal.shared import SwarmNodeDetails
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

        print(SwarmNode.objects.all())
        try:
            node = SwarmNode.objects.get(id=node_id)
        except SwarmNode.DoesNotExist:
            raise CommandError(f"A server with the id `{node_id}` does not exist")

        key = node.ssh_keys.filter(user="root").first()
        if key is None:
            raise CommandError(f"No Root SSH key found for the node `{node_id}`")

        self.stdout.write(
            f"Using Root SSH key {Colors.ORANGE}{key.name}{Colors.ENDC}"
            f" (id={key.id}, user={key.user})"
        )

        details = SwarmNodeDetails(
            private_ip=node.private_ip,
            role=node.role,  # type: ignore
            is_app_server=node.is_app_server,
            is_build_server=node.is_build_server,
            ssh_key=key.private_key,
            ssh_port=node.ssh_port,
        )

        workflow_id = f"provision-{node.id}-{int(time.time())}"
        self.stdout.write(
            f"{Colors.BLUE}Provisioning {details.private_ip}:{details.ssh_port}"
            f" as a {details.role}...{Colors.ENDC}"
        )

        result = async_to_sync(self.run_workflow)(details, workflow_id)
        self.stdout.write(f"{Colors.GREEN}Workflow finished ✅{Colors.ENDC} {result=}")

    async def run_workflow(self, details: SwarmNodeDetails, workflow_id: str):
        handle = await TemporalClient.astart_workflow(
            ProvisionSwarmNodeWorkflow.run,
            details,
            id=workflow_id,
        )
        self.stdout.write(
            f"Started workflow `{workflow_id}`, waiting for the result..."
        )
        return await handle.result(rpc_timeout=timedelta(seconds=30))
