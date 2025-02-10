from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal


@dataclass
class VolumeDto:
    container_path: str
    mode: Literal["READ_ONLY", "READ_WRITE"]
    name: Optional[str] = None
    host_path: Optional[str] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
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
    def from_dict(cls, data: Dict[str, Any]):
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
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class EnvVariableDto:
    key: str
    value: str
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class PortConfigurationDto:
    forwarded: int
    host: int = 0
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
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
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class DockerCredentialsDto:
    username: str
    password: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]):
        return cls(**data)

    def to_dict(self):
        return dict(username=self.username, password=self.password)


@dataclass
class MemoryLimitDto:
    unit: Literal["BYTES", "KILOBYTES", "MEGABYTES", "GIGABYTES"]
    value: int


@dataclass
class ResourceLimitsDto:
    cpus: Optional[float] = None
    memory: Optional[MemoryLimitDto] = None

    @classmethod
    def from_dict(cls, data: Dict[str, float | dict]):
        memory_dict = data.get("memory")
        memory = MemoryLimitDto(**memory_dict) if memory_dict is not None else None  # type: ignore
        return cls(
            cpus=data.get("cpus"),  # type: ignore
            memory=memory,
        )

    def to_dict(self):
        return dict(
            cpu=self.cpus,
            memory=(
                dict(
                    unit=self.memory.unit,
                    value=self.memory.value,
                )
                if self.memory is not None
                else None
            ),
        )


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
        return list(
            filter(
                lambda p: p.host is None or p.host in [80, 443],
                self.ports,
            )
        )

    @property
    def urls_with_associated_ports(self) -> List[URLDto]:
        return list(
            filter(
                lambda u: u.associated_port is not None,
                self.urls,
            )
        )

    @property
    def non_read_only_volumes(self) -> List[VolumeDto]:
        return list(filter(lambda v: v.mode != "READ_ONLY", self.volumes))

    @property
    def host_volumes(self) -> List[VolumeDto]:
        return list(filter(lambda v: v.host_path is not None, self.volumes))

    @property
    def docker_volumes(self) -> List[VolumeDto]:
        return list(filter(lambda v: v.host_path is None, self.volumes))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DockerServiceSnapshot":
        volumes = [VolumeDto.from_dict(item) for item in data.get("volumes", [])]
        configs = [ConfigDto.from_dict(item) for item in data.get("configs", [])]
        urls = [URLDto.from_dict(item) for item in data.get("urls", [])]
        ports = [PortConfigurationDto.from_dict(item) for item in data.get("ports", [])]
        env_variables = [
            EnvVariableDto.from_dict(item) for item in data.get("env_variables", [])
        ]
        healthcheck = (
            HealthCheckDto.from_dict(data["healthcheck"])
            if data.get("healthcheck") is not None
            else None
        )
        credentials = (
            DockerCredentialsDto.from_dict(data["credentials"])
            if data.get("credentials") is not None
            else None
        )
        resource_limits = (
            ResourceLimitsDto.from_dict(data["resource_limits"])
            if data.get("resource_limits") is not None
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

    def has_duplicate_volumes(self) -> bool:
        # Create dictionaries to keep track of seen host_paths and container_paths
        host_path_counts = defaultdict(int)
        container_path_counts = defaultdict(int)

        # Iterate through the volumes and count occurrences of host_path and container_path
        for volume in self.volumes:
            if volume.host_path is not None:
                host_path_counts[volume.host_path] += 1
            if volume.container_path is not None:
                container_path_counts[volume.container_path] += 1

        # Check if any host_path or container_path appears more than once
        has_duplicate_host_path = any(count > 1 for count in host_path_counts.values())
        has_duplicate_container_path = any(
            count > 1 for count in container_path_counts.values()
        )

        # Return True if there are duplicates in either host_path or container_path
        return has_duplicate_host_path or has_duplicate_container_path

    def has_duplicate_configs(self) -> bool:
        # Create dictionaries to keep track of seen host_paths and container_paths
        mount_path_counts = defaultdict(int)

        # Iterate through the volumes and count occurrences of host_path and container_path
        for config in self.configs:
            if config.mount_path is not None:
                mount_path_counts[config.mount_path] += 1

        # Check if any host_path or container_path appears more than once
        has_duplicate_mount_paths = any(
            count > 1 for count in mount_path_counts.values()
        )

        # Return True if there are duplicates in either host_path or container_path
        return has_duplicate_mount_paths


@dataclass
class DeploymentChangeDto:
    type: Literal["ADD", "UPDATE", "DELETE"]
    field: str
    item_id: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class RuntimeLogLevel:
    ERROR = "ERROR"
    INFO = "INFO"


class RuntimeLogSource:
    SYSTEM = "SYSTEM"
    PROXY = "PROXY"
    SERVICE = "SERVICE"


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
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)
