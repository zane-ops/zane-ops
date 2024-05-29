from dataclasses import dataclass, field
from typing import Literal, Any, Optional, List, Dict

from ..models import DockerRegistryService, BaseDeploymentChange
from ..serializers import DockerServiceSerializer


def compute_all_deployment_changes(service: DockerRegistryService, change: dict):
    deployment_changes = []
    deployment_changes.extend(
        map(
            lambda ch: DeploymentChangeDto.from_db_deployment_change(ch),
            service.unapplied_changes.all(),
        )
    )
    deployment_changes.append(DeploymentChangeDto(**change))
    return deployment_changes


def compute_docker_service_snapshot_from_changes(
    service: DockerRegistryService, change: dict
):
    deployment_changes = compute_all_deployment_changes(service, change)

    service_snapshot = DockerServiceSnapshot.from_serialized_data(
        DockerServiceSerializer(service).data
    )

    field_dto_map = {
        "volumes": VolumeDto,
        "env_variables": EnvVariableDto,
        "ports": PortConfigurationDto,
        "urls": URLDto,
    }
    for change in deployment_changes:
        match change.field:
            case "image" | "command":
                setattr(service_snapshot, change.field, change.new_value)
            case "healthcheck":
                service_snapshot.healthcheck = HealthCheckDto.from_dict(
                    change.new_value,
                )
            case "credentials":
                service_snapshot.credentials = DockerCredentialsDto.from_dict(
                    change.new_value
                )
            case _:
                dto_class: type[VolumeDto] = field_dto_map[change.field]
                items: list = getattr(service_snapshot, change.field)

                if change.type == "ADD":
                    items.append(dto_class.from_dict(change.new_value))
                if change.type == "DELETE":
                    setattr(
                        service_snapshot,
                        change.field,
                        [item for item in items if item.id != change.item_id],
                    )
                if change.type == "UPDATE":
                    for i, item in enumerate(items):
                        if item.id == change.item_id:
                            items[i] = dto_class.from_dict(
                                dict(change.new_value, id=change.item_id)
                            )

    return service_snapshot


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

    @classmethod
    def from_db_deployment_change(cls, change: BaseDeploymentChange):
        return cls(
            type=change.type,
            field=change.field,
            new_value=change.new_value,
            old_value=change.old_value,
            item_id=change.item_id,
        )


@dataclass
class VolumeDto:
    name: str
    container_path: str
    mode: Literal["READ_ONLY", "READ_WRITE"]
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
    command: Optional[str] = None
    healthcheck: Optional[HealthCheckDto] = None
    credentials: Optional[DockerCredentialsDto] = None
    volumes: List[VolumeDto] = field(default_factory=list)
    ports: List[PortConfigurationDto] = field(default_factory=list)
    env_variables: List[EnvVariableDto] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)

    @classmethod
    def from_serialized_data(cls, data: Dict[str, Any]) -> "DockerServiceSnapshot":
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
        )
