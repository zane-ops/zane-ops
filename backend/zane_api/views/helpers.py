import dataclasses
from dataclasses import dataclass, field, fields
from typing import Literal, Any, Optional, List, Dict

from django.db.models import Q

from ..models import DockerRegistryService, BaseDeploymentChange, DockerDeploymentChange
from ..serializers import DockerServiceSerializer


def compute_all_deployment_changes(
    service: DockerRegistryService, change: dict | None = None
):
    deployment_changes = []
    deployment_changes.extend(
        map(
            lambda ch: DeploymentChangeDto.from_db_deployment_change(ch),
            service.unapplied_changes.all(),
        )
    )
    if change is not None:
        deployment_changes.append(DeploymentChangeDto(**change))
    return deployment_changes


def compute_docker_service_snapshot_with_changes(
    service: DockerRegistryService, change: dict | None = None
):
    deployment_changes = compute_all_deployment_changes(service, change)

    service_snapshot = DockerServiceSnapshot.from_dict(
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


def compute_docker_service_snapshot_without_changes(
    service: DockerRegistryService, change_id: str
):
    deployment_changes = map(
        lambda ch: DeploymentChangeDto.from_db_deployment_change(ch),
        service.unapplied_changes.filter(~Q(id=change_id)),
    )

    service_snapshot = DockerServiceSnapshot.from_dict(
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


def compute_docker_changes_from_snapshots(current: dict, target: dict):
    current_snapshot = DockerServiceSnapshot.from_dict(current)
    target_snapshot = DockerServiceSnapshot.from_dict(target)

    changes: list[DockerDeploymentChange] = []

    for service_field in fields(current_snapshot):
        current_value = getattr(current_snapshot, service_field.name)
        target_value = getattr(target_snapshot, service_field.name)
        match service_field.name:
            case "image" | "command":
                if current_value != target_value:
                    changes.append(
                        DockerDeploymentChange(
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            field=service_field.name,
                            new_value=target_value,
                            old_value=current_value,
                        )
                    )
            case "healthcheck" | "credentials":
                if current_value != target_value:
                    changes.append(
                        DockerDeploymentChange(
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            field=service_field.name,
                            new_value=dataclasses.asdict(target_value),
                            old_value=dataclasses.asdict(current_value),
                        )
                    )
            case _:
                current_items: dict[
                    str, VolumeDto | URLDto | EnvVariableDto | PortConfigurationDto
                ] = {item.id: item for item in current_value}
                target_items: dict[
                    str, VolumeDto | URLDto | EnvVariableDto | PortConfigurationDto
                ] = {item.id: item for item in target_value}

                for item_id in current_items:
                    if item_id not in target_items:
                        changes.append(
                            DockerDeploymentChange(
                                type=DockerDeploymentChange.ChangeType.DELETE,
                                field=service_field.name,
                                item_id=item_id,
                                old_value=dataclasses.asdict(current_value),
                            )
                        )
                    elif current_items[item_id] != target_items[item_id]:
                        changes.append(
                            DockerDeploymentChange(
                                type=DockerDeploymentChange.ChangeType.UPDATE,
                                field=service_field.name,
                                item_id=item_id,
                                new_value=dataclasses.asdict(target_items[item_id]),
                                old_value=dataclasses.asdict(current_items[item_id]),
                            )
                        )

                    # Check for additions
                for item_id in target_items:
                    if item_id not in current_items:
                        element = target_items[item_id]
                        element.id = None
                        changes.append(
                            DockerDeploymentChange(
                                type=DockerDeploymentChange.ChangeType.ADD,
                                field=service_field.name,
                                new_value=dataclasses.asdict(element),
                            )
                        )
    return changes


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
    command: Optional[str] = None
    healthcheck: Optional[HealthCheckDto] = None
    credentials: Optional[DockerCredentialsDto] = None
    volumes: List[VolumeDto] = field(default_factory=list)
    ports: List[PortConfigurationDto] = field(default_factory=list)
    env_variables: List[EnvVariableDto] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)

    @property
    def http_ports(self):
        return list(
            filter(
                lambda p: p.host is None or p.host in [80, 443],
                self.ports,
            )
        )

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
        )
