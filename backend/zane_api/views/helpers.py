import dataclasses
from dataclasses import fields
from typing import Sequence

from django.db.models import Q

from ..dtos import (
    ConfigDto,
    DockerServiceSnapshot,
    VolumeDto,
    EnvVariableDto,
    PortConfigurationDto,
    URLDto,
    HealthCheckDto,
    DockerCredentialsDto,
    DeploymentChangeDto,
    ResourceLimitsDto,
)
from ..models import DockerRegistryService, DockerDeploymentChange
from ..serializers import DockerServiceSerializer


def compute_all_deployment_changes(
    service: DockerRegistryService, change: dict | None = None
):
    deployment_changes: list[DeploymentChangeDto] = []
    deployment_changes.extend(
        map(
            lambda ch: DeploymentChangeDto.from_dict(
                dict(
                    type=ch.type,
                    field=ch.field,
                    new_value=ch.new_value,
                    old_value=ch.old_value,
                    item_id=ch.item_id,
                )
            ),
            service.unapplied_changes.all(),
        )
    )
    if change is not None:
        deployment_changes.append(DeploymentChangeDto(**change))
    return deployment_changes


def compute_docker_service_snapshot(
    service_snapshot: DockerServiceSnapshot, changes: Sequence[DeploymentChangeDto]
):
    field_dto_map = {
        DockerDeploymentChange.ChangeField.VOLUMES: VolumeDto,
        DockerDeploymentChange.ChangeField.ENV_VARIABLES: EnvVariableDto,
        DockerDeploymentChange.ChangeField.PORTS: PortConfigurationDto,
        DockerDeploymentChange.ChangeField.URLS: URLDto,
        DockerDeploymentChange.ChangeField.CONFIGS: ConfigDto,
    }

    for change in changes:
        match change.field:
            case DockerDeploymentChange.ChangeField.COMMAND:
                setattr(service_snapshot, change.field, change.new_value)
            case DockerDeploymentChange.ChangeField.HEALTHCHECK:
                service_snapshot.healthcheck = (
                    HealthCheckDto.from_dict(
                        change.new_value,
                    )
                    if change.new_value is not None
                    else None
                )
            case DockerDeploymentChange.ChangeField.SOURCE:
                service_snapshot.image = change.new_value["image"]
                if change.new_value.get("credentials") is not None:
                    service_snapshot.credentials = (
                        DockerCredentialsDto.from_dict(change.new_value)
                        if change.new_value is not None
                        else None
                    )
            case DockerDeploymentChange.ChangeField.RESOURCE_LIMITS:
                service_snapshot.resource_limits = (
                    ResourceLimitsDto.from_dict(change.new_value)
                    if change.new_value is not None
                    else None
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


def compute_docker_service_snapshot_with_changes(
    service: DockerRegistryService, change: dict | None = None
):
    deployment_changes = compute_all_deployment_changes(service, change)

    service_snapshot = DockerServiceSnapshot.from_dict(
        DockerServiceSerializer(service).data
    )
    return compute_docker_service_snapshot(service_snapshot, deployment_changes)


def compute_docker_service_snapshot_without_changes(
    service: DockerRegistryService, change_id: str
):
    deployment_changes = map(
        lambda ch: DeploymentChangeDto.from_dict(
            dict(
                type=ch.type,
                field=ch.field,
                new_value=ch.new_value,
                old_value=ch.old_value,
                item_id=ch.item_id,
            )
        ),
        service.unapplied_changes.filter(~Q(id=change_id)),
    )

    service_snapshot = DockerServiceSnapshot.from_dict(
        DockerServiceSerializer(service).data
    )
    return compute_docker_service_snapshot(service_snapshot, deployment_changes)


def compute_docker_changes_from_snapshots(current: dict, target: dict):
    current_snapshot = DockerServiceSnapshot.from_dict(current)
    target_snapshot = DockerServiceSnapshot.from_dict(target)

    changes: list[DockerDeploymentChange] = []

    for service_field in fields(current_snapshot):
        current_value = getattr(current_snapshot, service_field.name)
        target_value = getattr(target_snapshot, service_field.name)
        match service_field.name:
            case "command":
                if current_value != target_value:
                    changes.append(
                        DockerDeploymentChange(
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            field=service_field.name,
                            new_value=target_value,
                            old_value=current_value,
                        )
                    )
            case "image" | "credentials":
                if current_value != target_value:
                    existing_change = next(
                        (change for change in changes if change.field == "source"),
                        None,
                    )
                    if existing_change is not None:
                        existing_change.new_value = {
                            "image": target_snapshot.image,
                            "credentials": (
                                target_snapshot.credentials.to_dict()
                                if target_snapshot.credentials is not None
                                else None
                            ),
                        }
                    else:
                        changes.append(
                            DockerDeploymentChange(
                                type=DockerDeploymentChange.ChangeType.UPDATE,
                                field=DockerDeploymentChange.ChangeField.SOURCE,
                                new_value={
                                    "image": target_snapshot.image,
                                    "credentials": (
                                        target_snapshot.credentials.to_dict()
                                        if target_snapshot.credentials is not None
                                        else None
                                    ),
                                },
                                old_value={
                                    "image": current_snapshot.image,
                                    "credentials": (
                                        current_snapshot.credentials.to_dict()
                                        if current_snapshot.credentials is not None
                                        else None
                                    ),
                                },
                            )
                        )
                    pass
            case "healthcheck":
                if current_value != target_value:
                    if target_value is not None and isinstance(
                        target_value, HealthCheckDto
                    ):
                        target_value.id = None
                    changes.append(
                        DockerDeploymentChange(
                            type=DockerDeploymentChange.ChangeType.UPDATE,
                            field=service_field.name,
                            new_value=(
                                dataclasses.asdict(target_value)
                                if target_value is not None
                                else None
                            ),
                            old_value=(
                                dataclasses.asdict(current_value)
                                if current_value is not None
                                else None
                            ),
                        )
                    )
            case "volumes" | "urls" | "env_variables" | "ports":
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
                                old_value=dataclasses.asdict(current_items[item_id]),
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


class ZaneServices:
    PROXY = "zane.proxy"
    API = "zane.api"
    WORKER = "zane.worker"
