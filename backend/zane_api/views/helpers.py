import dataclasses
from dataclasses import fields
from typing import Iterable, Sequence
from typing import cast

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
from ..models import Service, DeploymentChange
from ..serializers import DockerServiceSerializer


def compute_all_deployment_changes(service: Service, change: dict | None = None):
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
    service_snapshot: DockerServiceSnapshot,
    changes: Iterable[DeploymentChangeDto],
):
    field_dto_map = {
        DeploymentChange.ChangeField.VOLUMES: VolumeDto,
        DeploymentChange.ChangeField.ENV_VARIABLES: EnvVariableDto,
        DeploymentChange.ChangeField.PORTS: PortConfigurationDto,
        DeploymentChange.ChangeField.URLS: URLDto,
        DeploymentChange.ChangeField.CONFIGS: ConfigDto,
    }

    for change in changes:
        match change.field:
            case DeploymentChange.ChangeField.COMMAND:
                setattr(service_snapshot, change.field, change.new_value)
            case DeploymentChange.ChangeField.HEALTHCHECK:
                service_snapshot.healthcheck = (
                    HealthCheckDto.from_dict(
                        change.new_value,
                    )
                    if change.new_value is not None
                    else None
                )
            case DeploymentChange.ChangeField.SOURCE:
                service_snapshot.image = change.new_value["image"]  # type: ignore
                if change.new_value.get("credentials") is not None:  # type: ignore
                    service_snapshot.credentials = (
                        DockerCredentialsDto.from_dict(change.new_value)
                        if change.new_value is not None
                        else None
                    )
            case DeploymentChange.ChangeField.RESOURCE_LIMITS:
                service_snapshot.resource_limits = (
                    ResourceLimitsDto.from_dict(change.new_value)
                    if change.new_value is not None
                    else None
                )
            case _:
                dto_class: type[VolumeDto] = field_dto_map[change.field]  # type: ignore
                items: list = getattr(service_snapshot, change.field)

                if change.type == "ADD":
                    items.append(dto_class.from_dict(change.new_value))  # type: ignore
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
                                dict(change.new_value, id=change.item_id)  # type: ignore
                            )

    return service_snapshot


def compute_docker_service_snapshot_with_changes(
    service: Service, change: dict | None = None
):
    deployment_changes = compute_all_deployment_changes(service, change)

    service_snapshot = DockerServiceSnapshot.from_dict(
        DockerServiceSerializer(service).data  # type: ignore
    )
    return compute_docker_service_snapshot(service_snapshot, deployment_changes)


def compute_docker_service_snapshot_without_changes(service: Service, change_id: str):
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
        DockerServiceSerializer(service).data  # type: ignore
    )
    return compute_docker_service_snapshot(service_snapshot, deployment_changes)


def compute_docker_changes_from_snapshots(
    current: dict, target: dict
) -> list[DeploymentChange]:
    current_snapshot = DockerServiceSnapshot.from_dict(current)
    target_snapshot = DockerServiceSnapshot.from_dict(target)

    changes: list[DeploymentChange] = []

    for service_field in fields(current_snapshot):
        current_value = getattr(current_snapshot, service_field.name)
        target_value = getattr(target_snapshot, service_field.name)
        match service_field.name:
            case "command":
                if current_value != target_value:
                    changes.append(
                        DeploymentChange(
                            type=DeploymentChange.ChangeType.UPDATE,
                            field=service_field.name,
                            new_value=target_value,
                            old_value=current_value,
                        )
                    )
            case "image" | "credentials":
                if current_value != target_value:
                    existing_change = next(
                        (
                            change
                            for change in changes
                            if change.field == DeploymentChange.ChangeField.SOURCE
                        ),
                        None,
                    )
                    if existing_change is not None:
                        existing_change.new_value = {  # type: ignore
                            "image": target_snapshot.image,
                            "credentials": (
                                target_snapshot.credentials.to_dict()
                                if target_snapshot.credentials is not None
                                else None
                            ),
                        }
                    else:
                        changes.append(
                            DeploymentChange(
                                type=DeploymentChange.ChangeType.UPDATE,
                                field=DeploymentChange.ChangeField.SOURCE,
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
                    if target_value is not None:
                        # set associated port to the http port
                        target_value = cast(HealthCheckDto, target_value)
                        target_value.id = None

                        if (
                            target_value.associated_port is None
                            and target_value.type == "PATH"
                        ):
                            if len(target_snapshot.http_ports) > 0:
                                target_value.associated_port = (
                                    target_snapshot.http_ports[0].forwarded
                                )
                            # this is an invalid state, so we ignore it
                            else:
                                continue

                    changes.append(
                        DeploymentChange(
                            type=DeploymentChange.ChangeType.UPDATE,
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
            case "resource_limits":
                if current_value != target_value:
                    current_value = cast(ResourceLimitsDto, current_value)
                    if target_value is not None:
                        target_value = cast(ResourceLimitsDto, target_value)

                    changes.append(
                        DeploymentChange(
                            type=DeploymentChange.ChangeType.UPDATE,
                            field=service_field.name,
                            new_value=(
                                target_value.to_dict()
                                if target_value is not None
                                else None
                            ),
                            old_value=(
                                current_value.to_dict()
                                if current_value is not None
                                else None
                            ),
                        )
                    )
            case "volumes" | "urls" | "env_variables" | "ports" | "configs":
                current_items: dict[
                    str,
                    VolumeDto
                    | URLDto
                    | EnvVariableDto
                    | PortConfigurationDto
                    | ConfigDto,
                ] = {item.id: item for item in current_value}
                target_items: dict[
                    str,
                    VolumeDto
                    | URLDto
                    | EnvVariableDto
                    | PortConfigurationDto
                    | ConfigDto,
                ] = {item.id: item for item in target_value}

                for item_id in current_items:
                    if item_id not in target_items:
                        changes.append(
                            DeploymentChange(
                                type=DeploymentChange.ChangeType.DELETE,
                                field=service_field.name,
                                item_id=item_id,
                                old_value=dataclasses.asdict(current_items[item_id]),
                            )
                        )
                    elif current_items[item_id] != target_items[item_id]:
                        new_value = target_items[item_id]
                        old_value = current_items[item_id]

                        if service_field.name == "ports":
                            new_value = cast(PortConfigurationDto, new_value)
                            # Ignore http ports as they are not valid anymore
                            if new_value.host in [None, 80, 443]:
                                continue
                        if service_field.name == "urls":
                            # set associated port to the http port
                            new_value = cast(URLDto, new_value)
                            if (
                                new_value.associated_port is None
                                and new_value.redirect_to is None
                            ):
                                if len(target_snapshot.http_ports) > 0:
                                    new_value.associated_port = (
                                        target_snapshot.http_ports[0].forwarded
                                    )
                                # this is an invalid state, so we ignore it
                                else:
                                    continue
                        changes.append(
                            DeploymentChange(
                                type=DeploymentChange.ChangeType.UPDATE,
                                field=service_field.name,
                                item_id=item_id,
                                new_value=dataclasses.asdict(new_value),
                                old_value=dataclasses.asdict(old_value),
                            )
                        )

                # Check for additions
                for item_id in target_items:
                    if item_id not in current_items:
                        element = target_items[item_id]
                        element.id = None
                        if service_field.name == "ports":
                            element = cast(PortConfigurationDto, element)
                            # Ignore http ports as they are not valid anymore
                            if element.host in [None, 80, 443]:
                                continue
                        if service_field.name == "urls":
                            # set associated port to the http port
                            element = cast(URLDto, element)
                            if (
                                element.associated_port is None
                                and element.redirect_to is None
                            ):
                                if len(target_snapshot.http_ports) > 0:
                                    element.associated_port = (
                                        target_snapshot.http_ports[0].forwarded
                                    )
                                # this is an invalid state, so we ignore it
                                else:
                                    continue

                        changes.append(
                            DeploymentChange(
                                type=DeploymentChange.ChangeType.ADD,
                                field=service_field.name,
                                new_value=dataclasses.asdict(element),
                            )
                        )
    return changes


class ZaneServices:
    PROXY = "zane.proxy"
    API = "zane.api"
    WORKER = "zane.worker"
