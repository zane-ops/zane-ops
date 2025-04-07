from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional


from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ..models import Deployment

from ..dtos import (
    URLDto,
    DockerServiceSnapshot,
    DeploymentChangeDto,
    HealthCheckDto,
    VolumeDto,
    ConfigDto,
    StaticDirectoryBuilderOptions,
    DockerfileBuilderOptions,
)


@dataclass
class ProjectDetails:
    id: str


@dataclass
class ArchivedProjectDetails:
    id: int
    original_id: str


@dataclass
class DeploymentURLDto:
    domain: str
    port: int


@dataclass
class GitCloneDetails:
    deployment: "DeploymentDetails"
    location: str


@dataclass
class GitBuildDetails:
    deployment: "DeploymentDetails"
    temp_build_dir: str
    dockerfile_path: str
    build_context_dir: str
    build_stage_target: Optional[str] = None


@dataclass
class StaticBuilderDetails:
    builder_options: StaticDirectoryBuilderOptions
    temp_build_dir: str
    deployment: "DeploymentDetails"


@dataclass
class DockerfileBuilderDetails:
    builder_options: DockerfileBuilderOptions
    location: str
    deployment: "DeploymentDetails"


@dataclass
class DockerfileBuilderGeneratedResult:
    build_context_dir: str
    dockerfile_path: str


@dataclass
class StaticBuilderGeneratedResult:
    build_context_dir: str
    dockerfile_path: str
    caddyfile_path: str
    caddyfile_contents: str
    dockerfile_contents: str


@dataclass
class GitCommitDetails:
    author_name: str
    commit_message: str


@dataclass
class GitDeploymentDetailsWithCommitMessage:
    commit: GitCommitDetails
    deployment: "DeploymentDetails"


@dataclass
class DeploymentDetails:
    hash: str
    slot: str
    unprefixed_hash: str
    queued_at: str
    workflow_id: str
    service: DockerServiceSnapshot
    ignore_build_cache: bool = False
    urls: List[DeploymentURLDto] = field(default_factory=list)
    changes: List[DeploymentChangeDto] = field(default_factory=list)
    pause_at_step: int = 0
    network_alias: Optional[str] = None
    commit_sha: Optional[str] = None
    image_tag: Optional[str] = None

    @classmethod
    def from_deployment(cls, deployment: Deployment):
        return cls(
            hash=deployment.hash,
            slot=deployment.slot,
            queued_at=deployment.queued_at.isoformat(),
            commit_sha=deployment.commit_sha,
            image_tag=deployment.image_tag,
            ignore_build_cache=deployment.ignore_build_cache,
            unprefixed_hash=deployment.unprefixed_hash,
            urls=[DeploymentURLDto(domain=url.domain, port=url.port) for url in deployment.urls.all()],  # type: ignore
            service=DockerServiceSnapshot.from_dict(deployment.service_snapshot),  # type: ignore
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
                for change in deployment.changes.all()  # type: ignore
            ],
            workflow_id=deployment.workflow_id,
            network_alias=deployment.network_alias,
        )

    @classmethod
    async def afrom_deployment(
        cls,
        deployment: Deployment,
        pause_at_step: Enum | None = None,
    ):
        return cls(
            pause_at_step=pause_at_step.value if pause_at_step is not None else 0,
            hash=deployment.hash,
            slot=deployment.slot,
            queued_at=deployment.queued_at.isoformat(),
            commit_sha=deployment.commit_sha,
            image_tag=deployment.image_tag,
            ignore_build_cache=deployment.ignore_build_cache,
            unprefixed_hash=deployment.unprefixed_hash,
            urls=[DeploymentURLDto(domain=url.domain, port=url.port) async for url in deployment.urls.all()],  # type: ignore
            service=DockerServiceSnapshot.from_dict(deployment.service_snapshot),  # type: ignore
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
                async for change in deployment.changes.all()  # type: ignore
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
class DeploymentCreateConfigsResult:
    deployment_hash: str
    service_id: str
    created_configs: List[ConfigDto] = field(default_factory=list)


@dataclass
class SimpleDeploymentDetails:
    hash: str
    project_id: str
    service_id: str
    urls: List[str] = field(default_factory=list)
    status: Optional[str] = None
    service_snapshot: Optional[DockerServiceSnapshot] = None

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.project_id}"

    @property
    def metrics_schedule_id(self):
        return f"metrics-{self.hash}-{self.service_id}-{self.project_id}"


@dataclass
class SimpleGitDeploymentDetails:
    hash: str
    project_id: str
    service_id: str
    image_tag: str
    commit_sha: str
    urls: List[str] = field(default_factory=list)
    status: Optional[str] = None
    service_snapshot: Optional[DockerServiceSnapshot] = None

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.project_id}"

    @property
    def metrics_schedule_id(self):
        return f"metrics-{self.hash}-{self.service_id}-{self.project_id}"


@dataclass
class ToggleServiceDetails:
    deployment: SimpleDeploymentDetails
    desired_state: Literal["start", "stop"]


@dataclass
class EnvironmentDetails:
    id: str
    name: str
    project_id: str


@dataclass
class ArchivedDockerServiceDetails:
    original_id: str
    project_id: str
    deployments: List[SimpleDeploymentDetails] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)
    volumes: List[VolumeDto] = field(default_factory=list)
    configs: List[ConfigDto] = field(default_factory=list)


@dataclass
class ArchivedGitServiceDetails:
    original_id: str
    project_id: str
    deployments: List[SimpleGitDeploymentDetails] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)
    volumes: List[VolumeDto] = field(default_factory=list)
    configs: List[ConfigDto] = field(default_factory=list)


@dataclass
class HealthcheckDeploymentDetails:
    deployment: SimpleDeploymentDetails
    healthcheck: Optional[HealthCheckDto] = None


@dataclass
class ServiceMetricsResult:
    cpu_percent: float
    memory_bytes: int
    net_tx_bytes: int
    net_rx_bytes: int
    disk_read_bytes: int
    disk_writes_bytes: int
    deployment: SimpleDeploymentDetails


@dataclass
class DeployServiceWorkflowResult:
    deployment_status: str
    deployment_status_reason: str | None
    healthcheck_result: Optional[DeploymentHealthcheckResult] = None
    next_queued_deployment: Optional[DeploymentDetails] = None


@dataclass
class CancelDeploymentSignalInput:
    deployment_hash: str


@dataclass
class CleanupResult:
    deleted_count: int


@dataclass
class UpdateDetails:
    desired_version: str
    service_name: str
    service_image: str
