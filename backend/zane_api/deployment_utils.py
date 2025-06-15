from typing import Callable, List, Tuple
from django.db import transaction
from .models import Service, Deployment
from temporal.client import TemporalClient
from temporal.shared import CancelDeploymentSignalInput

# Assuming workflow paths are directly under temporal.workflows based on previous tasks
from temporal.workflows import DeployDockerServiceWorkflow, DeployGitServiceWorkflow


def cancel_active_deployments_for_services(services_list: List[Service]) -> None:
    """
    Cancels active deployments for a given list of services.
    - Directly sets status to CANCELLED if workflow hasn't started.
    - Sends a Temporal workflow signal if workflow has started.
    """
    active_statuses = [
        Deployment.DeploymentStatus.QUEUED,
        Deployment.DeploymentStatus.PREPARING,
        Deployment.DeploymentStatus.BUILDING,
        Deployment.DeploymentStatus.STARTING,
        Deployment.DeploymentStatus.RESTARTING,
    ]

    deployments_to_cancel = Deployment.objects.filter(
        service__in=services_list, status__in=active_statuses
    ).select_related("service")

    payloads: List[
        Tuple[
            CancelDeploymentSignalInput,
            Callable,  # workflow
            Callable,  # signal
            str,  # `workflow_id`
        ]
    ] = []

    for deployment in deployments_to_cancel:
        if deployment.started_at is None:
            deployment.status = Deployment.DeploymentStatus.CANCELLED
            deployment.status_reason = "Cancelled due to new superseding deployment."
            deployment.save()

        if deployment.service.type == Service.ServiceType.DOCKER_REGISTRY:
            payloads.append(
                (
                    CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                    DeployDockerServiceWorkflow.run,
                    DeployDockerServiceWorkflow.cancel_deployment,
                    deployment.workflow_id,
                )
            )

        else:
            payloads.append(
                (
                    CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                    DeployGitServiceWorkflow.run,
                    DeployGitServiceWorkflow.cancel_deployment,
                    deployment.workflow_id,
                )
            )

    transaction.on_commit(
        lambda: [
            TemporalClient.workflow_signal(
                workflow=payload[1],
                arg=payload[0],
                signal=payload[2],
                workflow_id=payload[3],
            )
            for payload in payloads
        ]
    )
