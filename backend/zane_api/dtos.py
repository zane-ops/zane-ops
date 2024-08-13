from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal


@dataclass
class VolumeDto:
    container_path: str
    mode: Literal["READ_ONLY", "READ_WRITE"]
    name: str = None
    host_path: Optional[str] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class URLDto:
    domain: str
    base_path: str
    strip_prefix: bool
    id: Optional[str] = None

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
    host: Optional[int] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class HealthCheckDto:
    type: str
    value: str
    timeout_seconds: int
    interval_seconds: int
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
    credentials: Optional[DockerCredentialsDto] = None
    volumes: List[VolumeDto] = field(default_factory=list)
    ports: List[PortConfigurationDto] = field(default_factory=list)
    env_variables: List[EnvVariableDto] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)

    @property
    def http_ports(self) -> List[PortConfigurationDto]:
        return list(
            filter(
                lambda p: p.host is None or p.host in [80, 443],
                self.ports,
            )
        )

    @property
    def http_port(self) -> PortConfigurationDto | None:
        ports = self.http_ports
        return ports[0] if len(ports) > 0 else None

    @property
    def non_http_ports(self) -> List[PortConfigurationDto]:
        return list(
            filter(
                lambda p: p.host is not None and p.host not in [80, 443],
                self.ports,
            )
        )

    @property
    def host_volumes(self) -> List[VolumeDto]:
        return list(filter(lambda v: v.host_path is not None, self.volumes))

    @property
    def docker_volumes(self) -> List[VolumeDto]:
        return list(filter(lambda v: v.host_path is None, self.volumes))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DockerServiceSnapshot":
        volumes = [VolumeDto.from_dict(item) for item in data.get("volumes", [])]
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

        return cls(
            image=data["image"],
            urls=urls,
            volumes=volumes,
            command=data.get("command"),
            ports=ports,
            env_variables=env_variables,
            healthcheck=healthcheck,
            credentials=credentials,
            id=data["id"],
            project_id=data["project_id"],
            network_aliases=data["network_aliases"],
            slug=data["slug"],
            network_alias=data["network_alias"],
        )


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
