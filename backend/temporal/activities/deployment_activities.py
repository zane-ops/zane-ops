from typing import List
from temporalio import activity, workflow


from ..shared import DeploymentDetails

with workflow.unsafe.imports_passed_through():
    from zane_api.models import Deployment
    from django.db.models import Q


@activity.defn
async def cancel_non_started_deployments(deployment: DeploymentDetails):
    previous_deployments = Deployment.objects.filter(
        service_id=deployment.service.id,
        status=(
            Q(started_at__isnull=True)
            & Q(finished_at__isnull=True)
            & Q(status=Deployment.DeploymentStatus.QUEUED)
            & Q(queued_at__lt=deployment.queued_at_as_datetime)
        ),
    ).select_related("service")

    await previous_deployments.aupdate(
        status=Deployment.DeploymentStatus.CANCELLED,
        status_reason="Deployment cancelled.",
    )
    return [dpl.hash async for dpl in previous_deployments]


@activity.defn
async def get_all_previous_cancellable_deployments(
    deployment: DeploymentDetails,
) -> List[DeploymentDetails]:
    previous_deployments = Deployment.objects.filter(
        service_id=deployment.service.id,
        status=(
            Q(finished_at__isnull=True)
            & Q(started_at__isnull=False)
            & Q(
                status__in=[
                    Deployment.DeploymentStatus.QUEUED,
                    Deployment.DeploymentStatus.PREPARING,
                    Deployment.DeploymentStatus.BUILDING,
                    Deployment.DeploymentStatus.STARTING,
                    Deployment.DeploymentStatus.RESTARTING,
                ],
            )
            & Q(queued_at__lt=deployment.queued_at_as_datetime)
        ),
    ).select_related("service")

    all_previous_cancellable_deployments: List[DeploymentDetails] = []

    async for dpl in previous_deployments:
        all_previous_cancellable_deployments.append(
            await DeploymentDetails.afrom_deployment(dpl)
        )

    return all_previous_cancellable_deployments
