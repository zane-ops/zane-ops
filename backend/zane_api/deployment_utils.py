from typing import List, Literal, Tuple
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
            type[DeployDockerServiceWorkflow] | type[DeployGitServiceWorkflow],
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
                    DeployDockerServiceWorkflow,
                    deployment.workflow_id,
                )
            )

            # transaction.on_commit(
            #     lambda: workflow_signal(
            #         workflow=DeployDockerServiceWorkflow.run,
            #         arg=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
            #         signal=DeployDockerServiceWorkflow.cancel_deployment,  # type: ignore
            #         workflow_id=deployment.workflow_id,
            #     )
            # )
        else:
            payloads.append(
                (
                    CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                    DeployGitServiceWorkflow,
                    deployment.workflow_id,
                )
            )

    transaction.on_commit(
        lambda: [
            TemporalClient.workflow_signal(
                workflow=payload[1].run,  # type: ignore
                arg=payload[0],
                signal=payload[1].cancel_deployment,  # type: ignore
                workflow_id=payload[2],
            )
            for payload in payloads
        ]
    )
    # transaction.on_commit(
    #     lambda: workflow_signal(
    #         workflow=DeployGitServiceWorkflow.run,
    #         arg=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
    #         signal=DeployGitServiceWorkflow.cancel_deployment,  # type: ignore
    #         workflow_id=deployment.workflow_id,
    #     )
    # )

    # else:
    #     if active_deployment.workflow_id:
    #         workflow_to_signal = None
    #         signal_to_use = None

    #         if (
    #             active_deployment.service.type
    #             == Service.ServiceType.DOCKER_REGISTRY
    #         ):
    #             workflow_to_signal = DeployDockerServiceWorkflow.run
    #             signal_to_use = DeployDockerServiceWorkflow.cancel_deployment
    #         elif (
    #             active_deployment.service.type == Service.ServiceType.GIT_REPOSITORY
    #         ):
    #             workflow_to_signal = DeployGitServiceWorkflow.run
    #             signal_to_use = DeployGitServiceWorkflow.cancel_deployment

    #         if workflow_to_signal and signal_to_use:
    #             # Use a lambda with default arguments to capture current values for the closure
    #             transaction.on_commit(
    #                 lambda ad=active_deployment, wf=workflow_to_signal, sig=signal_to_use: workflow_signal(
    #                     workflow=wf,
    #                     arg=CancelDeploymentSignalInput(deployment_hash=ad.hash),
    #                     signal=sig,  # type: ignore
    #                     workflow_id=ad.workflow_id,
    #                 )
    #             )
    #         else:
    #             # Fallback if service type is unknown or somehow no workflow/signal assigned
    #             # This case should ideally not happen if service types are exhaustive
    #             active_deployment.status = Deployment.DeploymentStatus.CANCELLED
    #             active_deployment.status_reason = (
    #                 "Cancelled (unknown service type for signal, fallback)."
    #             )
    #             active_deployment.save()
    #     else:
    #         # Fallback if workflow_id is somehow missing but deployment started
    #         active_deployment.status = Deployment.DeploymentStatus.CANCELLED
    #         active_deployment.status_reason = (
    #             "Cancelled (workflow_id missing, fallback)."
    #         )
    #         active_deployment.save()
