from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, Union, ClassVar
import logging

# Get the logger for this module
logger = logging.getLogger(__name__)


@dataclass
class VolumeDto:
    container_path: str
    mode: Literal["READ_ONLY", "READ_WRITE"]
    name: Optional[str] = None
    host_path: Optional[str] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VolumeDto":
        """Creates a VolumeDto from a dictionary."""
        return cls(**data)


@dataclass
class ConfigDto:
    mount_path: str
    contents: str
    language: str
    version: Optional[int] = 1
    name: Optional[str] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigDto":
        """Creates a ConfigDto from a dictionary."""
        return cls(**data)


@dataclass
class URLRedirectToDto:
    url: str
    permanent: bool = False


@dataclass
class URLDto:
    domain: str
    base_path: str
    strip_prefix: bool
    id: Optional[str] = None
    associated_port: Optional[int] = None
    redirect_to: Optional[URLRedirectToDto] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "URLDto":
        """Creates a URLDto from a dictionary."""
        return cls(**data)


@dataclass
class EnvVariableDto:
    key: str
    value: str
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvVariableDto":
        """Creates an EnvVariableDto from a dictionary."""
        return cls(**data)


@dataclass
class PortConfigurationDto:
    forwarded: int
    host: int = 0
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortConfigurationDto":
        """Creates a PortConfigurationDto from a dictionary."""
        return cls(**data)


@dataclass
class HealthCheckDto:
    type: Literal["PATH", "COMMAND"]
    value: str
    timeout_seconds: int
    interval_seconds: int
    associated_port: Optional[int] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthCheckDto":
        """Creates a HealthCheckDto from a dictionary."""
        return cls(**data)


@dataclass
class DockerCredentialsDto:
    username: str
    password: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "DockerCredentialsDto":
        """Creates a DockerCredentialsDto from a dictionary."""
        return cls(**data)

    def to_dict(self) -> Dict[str, str]:
        """Converts the DockerCredentialsDto to a dictionary."""
        return {"username": self.username, "password": self.password}


@dataclass
class MemoryLimitDto:
    unit: Literal["BYTES", "KILOBYTES", "MEGABYTES", "GIGABYTES"]
    value: int


@dataclass
class ResourceLimitsDto:
    cpus: Optional[float] = None
    memory: Optional[MemoryLimitDto] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Union[float, Dict[str, Any]]]) -> "ResourceLimitsDto":
        """Creates a ResourceLimitsDto from a dictionary."""
        memory_dict = data.get("memory")
        memory = MemoryLimitDto(**memory_dict) if memory_dict else None
        return cls(
            cpus=data.get("cpus"),
            memory=memory,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ResourceLimitsDto to a dictionary."""
        memory_dict = (
            {"unit": self.memory.unit, "value": self.memory.value}
            if self.memory
            else None
        )
        return {"cpus": self.cpus, "memory": memory_dict}


@dataclass
class DockerServiceSnapshot:
    image: str
    project_id: str
    id: str
    slug: str
    network_alias: str
    command: Optional[str] = None
    network_aliases: List[str] = field(default_factory=list)
    healthcheck: Optional[HealthCheckDto] = None
    resource_limits: Optional[ResourceLimitsDto] = None
    credentials: Optional[DockerCredentialsDto] = None
    volumes: List[VolumeDto] = field(default_factory=list)
    ports: List[PortConfigurationDto] = field(default_factory=list)
    env_variables: List[EnvVariableDto] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)
    configs: List[ConfigDto] = field(default_factory=list)

    @property
    def http_ports(self) -> List[PortConfigurationDto]:
        """Returns a list of HTTP ports."""
        return [
            p for p in self.ports if p.host is None or p.host in [80, 443]
        ]

    @property
    def urls_with_associated_ports(self) -> List[URLDto]:
        """Returns a list of URLs with associated ports."""
        return [u for u in self.urls if u.associated_port is not None]

    @property
    def non_read_only_volumes(self) -> List[VolumeDto]:
        """Returns a list of volumes that are not read-only."""
        return [v for v in self.volumes if v.mode != "READ_ONLY"]

    @property
    def host_volumes(self) -> List[VolumeDto]:
        """Returns a list of volumes with host paths."""
        return [v for v in self.volumes if v.host_path is not None]

    @property
    def docker_volumes(self) -> List[VolumeDto]:
        """Returns a list of volumes without host paths (Docker volumes)."""
        return [v for v in self.volumes if v.host_path is None]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DockerServiceSnapshot":
        """Creates a DockerServiceSnapshot from a dictionary."""
        try:
            volumes = [VolumeDto.from_dict(item) for item in data.get("volumes", [])]
            configs = [ConfigDto.from_dict(item) for item in data.get("configs", [])]
            urls = [URLDto.from_dict(item) for item in data.get("urls", [])]
            ports = [PortConfigurationDto.from_dict(item) for item in data.get("ports", [])]
            env_variables = [
                EnvVariableDto.from_dict(item) for item in data.get("env_variables", [])
            ]
            healthcheck = (
                HealthCheckDto.from_dict(data["healthcheck"])
                if data.get("healthcheck")
                else None
            )
            credentials = (
                DockerCredentialsDto.from_dict(data["credentials"])
                if data.get("credentials")
                else None
            )
            resource_limits = (
                ResourceLimitsDto.from_dict(data["resource_limits"])
                if data.get("resource_limits")
                else None
            )

            return cls(
                image=data["image"],
                urls=urls,
                volumes=volumes,
                configs=configs,
                command=data.get("command"),
                ports=ports,
                env_variables=env_variables,
                healthcheck=healthcheck,
                credentials=credentials,
                resource_limits=resource_limits,
                id=data["id"],
                project_id=data["project_id"],
                network_aliases=data["network_aliases"],
                slug=data["slug"],
                network_alias=data["network_alias"],
            )
        except KeyError as e:
            logger.error(f"Missing key in data: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating DockerServiceSnapshot from dict: {e}")
            raise

    def has_duplicate_volumes(self) -> bool:
        """Checks if there are duplicate volumes based on host_path or container_path."""
        host_path_counts: Dict[str, int] = defaultdict(int)
        container_path_counts: Dict[str, int] = defaultdict(int)

        for volume in self.volumes:
            if volume.host_path:
                host_path_counts[volume.host_path] += 1
            if volume.container_path:
                container_path_counts[volume.container_path] += 1

        has_duplicate_host_path = any(count > 1 for count in host_path_counts.values())
        has_duplicate_container_path = any(count > 1 for count in container_path_counts.values())

        return has_duplicate_host_path or has_duplicate_container_path

    def has_duplicate_configs(self) -> bool:
        """Checks if there are duplicate configs based on mount_path."""
        mount_path_counts: Dict[str, int] = defaultdict(int)

        for config in self.configs:
            if config.mount_path:
                mount_path_counts[config.mount_path] += 1

        has_duplicate_mount_paths = any(count > 1 for count in mount_path_counts.values())

        return has_duplicate_mount_paths

    @property
    def duplicate_envs(self) -> List[str]:
        """Returns a list of duplicate environment variable keys."""
        env_values: Dict[str, int] = defaultdict(int)

        for env in self.env_variables:
            env_values[env.key] += 1

        return [key for key, value in env_values.items() if value > 1]


@dataclass
class DeploymentChangeDto:
    type: Literal["ADD", "UPDATE", "DELETE"]
    field: str
    item_id: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeploymentChangeDto":
        """Creates a DeploymentChangeDto from a dictionary."""
        return cls(**data)


class RuntimeLogLevel:
    ERROR: ClassVar[str] = "ERROR"
    INFO: ClassVar[str] = "INFO"


class RuntimeLogSource:
    SYSTEM: ClassVar[str] = "SYSTEM"
    PROXY: ClassVar[str] = "PROXY"
    SERVICE: ClassVar[str] = "SERVICE"


@dataclass
class RuntimeLogDto:
    id: str
    created_at: str
    time: str
    level: Literal["ERROR", "INFO"]
    source: Literal["SYSTEM", "PROXY", "SERVICE"]
    service_id: Optional[str] = None
    deployment_id: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeLogDto":
        """Creates a RuntimeLogDto from a dictionary."""
        return cls(**data)
