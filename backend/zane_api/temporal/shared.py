from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
    ConfigDto,
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
    unprefixed_hash: str
    queued_at: str
    workflow_id: str
    service: DockerServiceSnapshot
    url: Optional[str] = None
    changes: List[DeploymentChangeDto] = field(default_factory=list)
    pause_at_step: int = 0
    network_alias: Optional[str] = None

    @classmethod
    def from_deployment(cls, deployment: DockerDeployment):
        return cls(
            hash=deployment.hash,
            slot=deployment.slot,
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
            workflow_id=deployment.workflow_id,
            network_alias=deployment.network_alias,
        )

    @classmethod
    async def afrom_deployment(
        cls,
        deployment: DockerDeployment,
        pause_at_step: Enum = None,
    ):
        return cls(
            pause_at_step=pause_at_step.value if pause_at_step is not None else 0,
            hash=deployment.hash,
            slot=deployment.slot,
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
                async for change in deployment.changes.all()
            ],
            workflow_id=deployment.workflow_id,
            network_alias=deployment.network_alias,
        )

    @property
    def queued_at_as_datetime(self):
        return datetime.fromisoformat(self.queued_at)


@dataclass
class DeploymentHealthcheckResult:
    deployment_hash: str
    status: str
    service_id: str
    reason: Optional[str] = None


@dataclass
class DeploymentCreateVolumesResult:
    deployment_hash: str
    service_id: str
    created_volumes: List[VolumeDto] = field(default_factory=list)


@dataclass
class SimpleDeploymentDetails:
    hash: str
    project_id: str
    service_id: str
    status: Optional[str] = None
    url: Optional[str] = None
    service_snapshot: Optional[DockerServiceSnapshot] = None

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.project_id}"


@dataclass
class ArchivedServiceDetails:
    original_id: str
    project_id: str
    deployments: List[SimpleDeploymentDetails] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)
    volumes: List[VolumeDto] = field(default_factory=list)
    configs: List[ConfigDto] = field(default_factory=list)


@dataclass
class HealthcheckDeploymentDetails:
    deployment: SimpleDeploymentDetails
    healthcheck: Optional[HealthCheckDto] = None


@dataclass
class DeployDockerServiceWorkflowResult:
    deployment_status: str
    deployment_status_reason: str
    healthcheck_result: Optional[DeploymentHealthcheckResult] = None
    next_queued_deployment: Optional[DockerDeploymentDetails] = None


@dataclass
class CancelDeploymentSignalInput:
    deployment_hash: str


@dataclass
class LogsCleanupResult:
    deleted_count: int
