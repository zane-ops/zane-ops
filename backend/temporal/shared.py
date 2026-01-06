from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional, TYPE_CHECKING, cast
import yaml


if TYPE_CHECKING:
    from zane_api.models import Deployment
    from compose.models import ComposeStackDeployment

from zane_api.dtos import (
    URLDto,
    ServiceSnapshot,
    DeploymentChangeDto,
    HealthCheckDto,
    VolumeDto,
    ConfigDto,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
    DockerfileBuilderOptions,
    EnvVariableDto,
)
from compose.dtos import (
    ComposeStackServiceStatusDto,
    ComposeStackSpec,
    ComposeStackSnapshot,
)

from .constants import (
    BUILD_REGISTRY_VOLUME_PATH,
    ZANEOPS_SLEEP_DEPLOY_MARKER,
    ZANEOPS_RESUME_DEPLOY_MARKER,
    BUILD_REGISTRY_PASSWORD_PATH,
)


@dataclass
class ProjectDetails:
    id: str


@dataclass
class ArchivedProjectDetails:
    id: int
    original_id: str
    environments: List["EnvironmentDetails"]


@dataclass
class DeploymentURLDto:
    domain: str
    port: int


@dataclass
class GitCloneDetails:
    deployment: "DeploymentDetails"
    tmp_dir: str


@dataclass
class GitBuildDetails:
    deployment: "DeploymentDetails"
    temp_build_dir: str
    dockerfile_path: str
    build_context_dir: str
    image_tag: str
    build_stage_target: Optional[str] = None
    default_env_variables: List[EnvVariableDto] | None = None


@dataclass
class StaticBuilderDetails:
    builder_options: StaticDirectoryBuilderOptions
    temp_build_dir: str
    deployment: "DeploymentDetails"


@dataclass
class NixpacksBuilderDetails:
    builder_options: NixpacksBuilderOptions
    temp_build_dir: str
    deployment: "DeploymentDetails"


@dataclass
class RailpackBuilderDetails:
    builder_options: NixpacksBuilderOptions
    temp_build_dir: str
    deployment: "DeploymentDetails"


@dataclass
class DockerfileBuilderDetails:
    builder_options: DockerfileBuilderOptions
    temp_build_dir: str
    deployment: "DeploymentDetails"


@dataclass
class DockerfileBuilderGeneratedResult:
    build_context_dir: str
    dockerfile_path: str
    env_file_path: str
    env_file_contents: str


@dataclass
class StaticBuilderGeneratedResult:
    build_context_dir: str
    dockerfile_path: str
    caddyfile_path: str
    caddyfile_contents: str
    dockerfile_contents: str


@dataclass
class NixpacksBuilderGeneratedResult:
    build_context_dir: str
    dockerfile_path: str
    dockerfile_contents: str
    nixpacks_plan_contents: dict
    caddyfile_path: Optional[str] = None
    caddyfile_contents: Optional[str] = None
    variables: List[EnvVariableDto] = field(default_factory=list)


@dataclass
class RailpackBuilderGeneratedResult:
    build_context_dir: str
    railpack_plan_contents: dict
    railpack_plan_path: str
    railpack_custom_config_path: Optional[str] = None
    railpack_custom_config_contents: Optional[dict] = None
    caddyfile_contents: Optional[str] = None


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
    service: ServiceSnapshot
    ignore_build_cache: bool = False
    urls: List[DeploymentURLDto] = field(default_factory=list)
    changes: List[DeploymentChangeDto] = field(default_factory=list)
    pause_at_step: int = 0
    network_alias: Optional[str] = None
    commit_sha: Optional[str] = None
    image_tag: Optional[str] = None

    @classmethod
    def from_deployment(cls, deployment: "Deployment"):
        return cls(
            hash=deployment.hash,
            slot=deployment.slot,
            queued_at=deployment.queued_at.isoformat(),
            commit_sha=deployment.commit_sha,
            image_tag=deployment.image_tag,
            ignore_build_cache=deployment.ignore_build_cache,
            unprefixed_hash=deployment.unprefixed_hash,
            urls=[
                DeploymentURLDto(domain=url.domain, port=url.port)
                for url in deployment.urls.all()
            ],  # type: ignore
            service=ServiceSnapshot.from_dict(deployment.service_snapshot),  # type: ignore
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
        deployment: "Deployment",
        pause_at_step: Enum | None = None,
    ):
        return cls(
            pause_at_step=pause_at_step.value if pause_at_step is not None else 0,
            hash=deployment.hash,
            slot=deployment.slot,
            queued_at=deployment.queued_at.isoformat(),
            commit_sha=deployment.commit_sha,
            image_tag=await deployment.aimage_tag,
            ignore_build_cache=deployment.ignore_build_cache,
            unprefixed_hash=deployment.unprefixed_hash,
            urls=[
                DeploymentURLDto(domain=url.domain, port=url.port)
                async for url in deployment.urls.all()
            ],  # type: ignore
            service=ServiceSnapshot.from_dict(deployment.service_snapshot),  # type: ignore
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
class DeploymentResult:
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
    service_snapshot: Optional[ServiceSnapshot] = None

    @property
    def monitor_schedule_id(self):
        return f"monitor-{self.hash}-{self.service_id}-{self.project_id}"

    @property
    def metrics_schedule_id(self):
        return f"metrics-{self.hash}-{self.service_id}-{self.project_id}"


@dataclass
class ScaleBackServiceDetails(SimpleDeploymentDetails):
    wake_up_if_sleeping: bool = False
    status_marker: str = ZANEOPS_RESUME_DEPLOY_MARKER

    @classmethod
    def from_simple_deployment_details(
        cls,
        details: SimpleDeploymentDetails,
        wake_up_if_sleeping: bool = False,
        status_marker: str = ZANEOPS_RESUME_DEPLOY_MARKER,
    ):
        return cls(
            hash=details.hash,
            project_id=details.project_id,
            service_id=details.service_id,
            urls=details.urls,
            status=details.status,
            service_snapshot=details.service_snapshot,
            wake_up_if_sleeping=wake_up_if_sleeping,
            status_marker=status_marker,
        )


@dataclass
class ScaleDownServiceDetails(SimpleDeploymentDetails):
    status_marker: str = ZANEOPS_SLEEP_DEPLOY_MARKER

    @classmethod
    def from_simple_deployment_details(
        cls,
        details: SimpleDeploymentDetails,
        status_marker: str = ZANEOPS_SLEEP_DEPLOY_MARKER,
    ):
        return cls(
            hash=details.hash,
            project_id=details.project_id,
            service_id=details.service_id,
            urls=details.urls,
            status=details.status,
            service_snapshot=details.service_snapshot,
            status_marker=status_marker,
        )


@dataclass
class SimpleGitDeploymentDetails:
    hash: str
    project_id: str
    service_id: str
    image_tag: str
    commit_sha: str
    urls: List[str] = field(default_factory=list)
    status: Optional[str] = None
    service_snapshot: Optional[ServiceSnapshot] = None

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

    @property
    def archive_workflow_id(self) -> str:
        return f"archive-env-{self.project_id}-{self.id}"


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
    result: Optional[DeploymentResult] = None
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
    wait_for_update: bool = False


@dataclass
class UpdateOnGoingDetails:
    ongoing: bool


@dataclass
class BuildRegistryDetails:
    registry_url: str
    registry_username: str
    registry_password: str
    deployment: DeploymentDetails


@dataclass
class RegistryConfig:
    @dataclass
    class LogConfig:
        @dataclass
        class LogFields:
            service: str = "registry"
            environment: str = "production"

        level: str = "debug"
        fields: LogFields = field(default_factory=LogFields)

    @dataclass
    class StorageConfig:
        @dataclass
        class DeleteConfig:
            enabled: bool = True

        @dataclass
        class CacheConfig:
            blobdescriptor: str = "inmemory"

        @dataclass
        class Filesystem:
            rootdirectory: str = BUILD_REGISTRY_VOLUME_PATH

        @dataclass
        class S3:
            bucket: str
            accesskey: str
            secretkey: str
            secure: bool = True
            region: str = "us-west-1"
            regionendpoint: Optional[str] = None
            loglevel: Literal["debug"] = "debug"

            def to_dict(self):
                config = asdict(self)
                if config["regionendpoint"] is None:
                    config.pop("regionendpoint")
                return config

        @dataclass
        class TagConfig:
            concurrencylimit: int = 5

        delete: DeleteConfig = field(default_factory=DeleteConfig)
        cache: CacheConfig = field(default_factory=CacheConfig)
        filesystem: Optional[Filesystem] = None
        s3: Optional[S3] = None
        tag: TagConfig = field(default_factory=TagConfig)

        def to_dict(self):
            config = asdict(self)

            # remove `None` option so that they don't appear as `null` but instead get omited
            if config["filesystem"] is None:
                config.pop("filesystem")
            if config["s3"] is None:
                config.pop("s3")

            if self.s3 is not None:
                config["s3"] = self.s3.to_dict()
            return config

    @dataclass
    class HttpConfig:
        @dataclass
        class DebugConfig:
            addr: str = ":5001"

        addr: str = ":5000"
        debug: DebugConfig = field(default_factory=DebugConfig)

    @dataclass
    class HealthCheckConfig:
        @dataclass
        class StorageDriverCheck:
            enabled: bool = True
            interval: str = "30s"
            threshold: int = 3

        storagedriver: StorageDriverCheck = field(default_factory=StorageDriverCheck)

    @dataclass
    class RegistryAuth:
        @dataclass
        class Htpasswd:
            realm: str = "Registry Realm"
            path: str = BUILD_REGISTRY_PASSWORD_PATH

        htpasswd: Htpasswd = field(default_factory=Htpasswd)

    version: float = 0.1
    log: LogConfig = field(default_factory=LogConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    health: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    auth: RegistryAuth = field(default_factory=RegistryAuth)

    def to_yaml(self):
        cfg = asdict(self)
        cfg["storage"] = self.storage.to_dict()
        return yaml.safe_dump(cfg, default_flow_style=False, sort_keys=False)


@dataclass
class RegistrySnaphot:
    id: str
    name: str
    config: RegistryConfig
    domain: str
    username: str
    password: str
    version: int
    service_alias: str
    swarm_service_name: str
    is_secure: bool
    monitor_schedule_id: str


@dataclass
class UpdateRegistryPayload:
    service_alias: str
    swarm_service_name: str
    id: str
    previous: RegistrySnaphot
    current: RegistrySnaphot


@dataclass
class CreateBuildRegistryConfigsDetails:
    configs: list[ConfigDto]


@dataclass
class SwarmRegistryServiceDetails:
    alias: str
    swarm_id: str
    configs: dict[str, ConfigDto]
    registry: RegistrySnaphot
    volume: Optional[VolumeDto] = None


@dataclass
class DeleteSwarmRegistryServiceDetails:
    swarm_service_name: str
    service_alias: str
    domain: str
    monitor_schedule_id: str


@dataclass
class DeleteSwarmRegistryDomainDetails:
    service_alias: str
    domain: str


@dataclass
class RegistryHealthCheckResult:
    id: str
    status: str
    reason: Optional[str] = None


@dataclass
class ComposeStackDeploymentDetails:
    hash: str
    stack: ComposeStackSnapshot

    @classmethod
    def from_deployment(
        cls,
        deployment: "ComposeStackDeployment",
    ):
        snapshot = ComposeStackSnapshot.from_dict(cast(dict, deployment.stack_snapshot))
        return cls(
            hash=deployment.hash,
            stack=snapshot,
        )

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            hash=data["hash"],
            stack=ComposeStackSnapshot.from_dict(data["stack"]),
        )


@dataclass
class ComposeStackBuildDetails:
    tmp_build_dir: str
    deployment: ComposeStackDeploymentDetails

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            tmp_build_dir=data["tmp_build_dir"],
            deployment=ComposeStackDeploymentDetails.from_dict(data["deployment"]),
        )


@dataclass
class ComposeStackHealthcheckResult:
    id: str
    services: Dict[str, ComposeStackServiceStatusDto]


@dataclass
class ComposeStackMonitorPayload:
    status: str
    status_message: str
    deployment: ComposeStackDeploymentDetails
