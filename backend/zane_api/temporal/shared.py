from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from django.conf import settings
    from ..models import DockerDeployment

from ..dtos import (
    URLDto,
    DockerServiceSnapshot,
    DeploymentChangeDto,
    HealthCheckDto,
    VolumeDto,
)


@dataclass
class ProjectDetails:
    id: str


@dataclass
class ArchivedProjectDetails:
    id: int
    original_id: str


@dataclass
class DockerDeploymentDetails:
    hash: str
    slot: str
    auth_token: str
    unprefixed_hash: str
    queued_at: str
    service: DockerServiceSnapshot
    url: Optional[str] = None
    changes: List[DeploymentChangeDto] = field(default_factory=list)
    pause_at_step: int = 0

    @property
    def workflow_id(self):
        return f"deploy-{self.service.id}-{self.service.project_id}"

    @classmethod
    def from_deployment(
        cls,
        deployment: DockerDeployment,
        auth_token: str,
        _pause_at_step: int = 0,
    ):
        return cls(
            pause_at_step=_pause_at_step,
            hash=deployment.hash,
            slot=deployment.slot,
            auth_token=auth_token,
            queued_at=deployment.queued_at.isoformat(),
            unprefixed_hash=deployment.unprefixed_hash,
            url=deployment.url,
            service=DockerServiceSnapshot.from_dict(deployment.service_snapshot),
            changes=[
                DeploymentChangeDto.from_dict(
                    dict(
                        type=change.type,
                        field=change.field,
                        new_value=change.new_value,
                        old_value=change.old_value,
                        item_id=change.item_id,
                    )
                )
                for change in deployment.changes.all()
            ],
        )

    @property
    def queued_at_as_datetime(self):
        return datetime.fromisoformat(self.queued_at)

    @property
    def network_aliases(self):
        aliases = []
        if self.service is not None and len(self.service.network_aliases) > 0:
            aliases = self.service.network_aliases + [
                f"{self.service.network_alias}.{self.slot.lower()}.{settings.ZANE_INTERNAL_DOMAIN}",
            ]
        return aliases


@dataclass
class DeploymentHealthcheckResult:
    deployment_hash: str
    status: str
    service_id: str
    reason: Optional[str] = None


@dataclass
class SimpleDeploymentDetails:
    hash: str
    project_id: str
    service_id: str
    status: Optional[str] = None
    url: Optional[str] = None

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.project_id}"


@dataclass
class ArchivedServiceDetails:
    original_id: str
    project_id: str
    deployments: List[SimpleDeploymentDetails] = field(default_factory=list)
    deployment_urls: List[str] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)
    volumes: List[VolumeDto] = field(default_factory=list)


@dataclass
class HealthcheckDeploymentDetails:
    deployment: SimpleDeploymentDetails
    auth_token: str
    healthcheck: Optional[HealthCheckDto] = None


@dataclass
class CancelDeploymentResult:
    success: bool
    message: Optional[str] = None


@dataclass
class DeployDockerServiceWorkflowResult:
    deployment_status: str
    healthcheck_result: Optional[DeploymentHealthcheckResult] = None
    next_queued_deployment: Optional[DockerDeploymentDetails] = None
