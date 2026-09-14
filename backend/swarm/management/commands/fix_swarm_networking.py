from typing import Any, Callable, List, Tuple

import docker.errors
from django.core.management.base import BaseCommand
from django.db import transaction

from compose.models import ComposeStack, ComposeStackDeployment
from temporal.client import TemporalClient
from temporal.helpers import (
    get_docker_client,
    get_env_network_resource_name,
    get_resource_labels,
)
from temporal.shared import ComposeStackDeploymentDetails, DeploymentDetails
from temporal.workflows import (
    DeployComposeStackWorkflow,
    DeployDockerServiceWorkflow,
    DeployGitServiceWorkflow,
)
from zane_api.models import Environment, Service, Deployment
from zane_api.utils import Colors
from compose.dtos import ComposeStackServiceStatus
from temporalio.exceptions import WorkflowAlreadyStartedError


class Command(BaseCommand):
    help = (
        "Recover from a full swarm rebuild after changing this manager's "
        "`--advertise-addr` (`docker swarm leave -f` + `docker swarm init "
        "--advertise-addr <new-ip>`, which wipes every network and service known "
        "to Swarm): recreate every environment's overlay network, then redeploy "
        "every service and compose stack from ZaneOps' own records so the cluster "
        "matches what's in the database again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the confirmation prompt.",
        )
        parser.add_argument(
            "--force-redeploy",
            action="store_true",
            help="Redeploy all services",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            confirm = input(
                f"{Colors.ORANGE}This will redeploy every service and compose "
                f"stack on this instance. Continue? [y/N]: {Colors.ENDC}"
            )
            if confirm.lower() not in ("y", "yes"):
                self.stdout.write("Aborted.")
                return

        self.recreate_environment_networks()
        if options.get("force_redeploy"):
            self.redeploy_all_services()
            self.redeploy_all_compose_stacks()

    def recreate_environment_networks(self):
        docker_client = get_docker_client()

        self.stdout.write(f"{Colors.BLUE}Checking environment networks...{Colors.ENDC}")
        for env in Environment.objects.select_related("project").all():
            network_name = get_env_network_resource_name(
                env.id, project_id=env.project_id
            )
            try:
                docker_client.networks.get(network_name)
                self.stdout.write(f"  `{network_name}` already exists, skipping")
            except docker.errors.NotFound:
                is_production = env.name == Environment.PRODUCTION_ENV_NAME
                docker_client.networks.create(
                    name=network_name,
                    scope="swarm",
                    driver="overlay",
                    labels=get_resource_labels(
                        env.project_id,
                        **({"is_production": "True"} if is_production else {}),
                    ),
                    attachable=True,
                )
                self.stdout.write(
                    f"  {Colors.GREEN}recreated `{network_name}`{Colors.ENDC}"
                )

    @transaction.atomic()
    def redeploy_all_services(self):
        self.stdout.write(f"{Colors.BLUE}Redeploying all services...{Colors.ENDC}")

        services = (
            Service.objects.all()
            .select_related("healthcheck", "project", "environment")
            .prefetch_related(
                "volumes",
                "ports",
                "urls",
                "env_variables",
                "changes",
                "configs",
                "git_app",
            )
        )

        sleeping_deployments = (
            Deployment.objects.filter(
                is_current_production=True, status=Deployment.DeploymentStatus.SLEEPING
            )
            .order_by("service_id")
            .distinct("service_id")
            .all()
        )

        sleeping_services_dict = {dpl.service_id for dpl in sleeping_deployments}

        workflows_to_run: List[Tuple[Callable, DeploymentDetails, str]] = []
        for service in services:
            if service.id in sleeping_services_dict:
                continue

            if service.type == Service.ServiceType.DOCKER_REGISTRY:
                new_deployment = service.prepare_new_docker_deployment(
                    commit_message="redeploy after swarm state recovery",
                )
                workflow = DeployDockerServiceWorkflow.run
            else:
                new_deployment = service.prepare_new_git_deployment()
                workflow = DeployGitServiceWorkflow.run

            payload = DeploymentDetails.from_deployment(deployment=new_deployment)
            workflows_to_run.append((workflow, payload, payload.workflow_id))

        def commit_callback():
            for workflow, payload, workflow_id in workflows_to_run:
                try:
                    TemporalClient.start_workflow(workflow, payload, workflow_id)
                except WorkflowAlreadyStartedError as e:
                    self.stdout.write(
                        f"  {Colors.GREEN}Redeploy for `{Colors.GREEN}{payload.hash}{Colors.ENDC}`({Colors.YELLOW}{payload.service.slug}{Colors.ENDC}){Colors.ENDC} is already Queued"
                    )
                else:
                    self.stdout.write(
                        f"  queued redeploy for `{Colors.GREEN}{payload.hash}{Colors.ENDC}`({Colors.YELLOW}{payload.service.slug}{Colors.ENDC}){Colors.ENDC}"
                    )

        transaction.on_commit(commit_callback)

    @transaction.atomic()
    def redeploy_all_compose_stacks(self):
        self.stdout.write(
            f"{Colors.BLUE}Redeploying all compose stacks...{Colors.ENDC}"
        )

        stacks = ComposeStack.objects.all().prefetch_related("changes", "env_overrides")

        workflows_to_run: List[Tuple[ComposeStackDeploymentDetails, str]] = []
        for stack in stacks:
            is_stack_sleeping = all(
                stack.services[service].get("status")
                == ComposeStackServiceStatus.SLEEPING
                for service in dict(stack.services)
            )
            if is_stack_sleeping:
                continue

            deployment = ComposeStackDeployment.objects.create(
                commit_message="redeploy after swarm state recovery",
                stack=stack,
            )
            stack.apply_pending_changes(deployment=deployment)
            deployment.stack_snapshot = stack.snapshot.to_dict()  # type: ignore
            deployment.save()

            payload = ComposeStackDeploymentDetails.from_deployment(
                deployment=deployment
            )
            workflows_to_run.append((payload, payload.workflow_id))

        def commit_callback():
            for payload, workflow_id in workflows_to_run:
                try:
                    TemporalClient.start_workflow(
                        DeployComposeStackWorkflow.run, payload, workflow_id
                    )
                except WorkflowAlreadyStartedError as e:
                    self.stdout.write(
                        f"  Redeploy for `{Colors.GREEN}{payload.hash}{Colors.ENDC}`({Colors.YELLOW}{payload.stack.slug}{Colors.ENDC}){Colors.ENDC} is already Queued"
                    )
                else:
                    self.stdout.write(
                        f"  queued redeploy for `{Colors.GREEN}{payload.hash}{Colors.ENDC}`({Colors.YELLOW}{payload.stack.slug}{Colors.ENDC}){Colors.ENDC}"
                    )

        transaction.on_commit(commit_callback)
