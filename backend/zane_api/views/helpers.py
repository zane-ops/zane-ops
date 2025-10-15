import dataclasses
from dataclasses import fields
from typing import Iterable
from typing import cast

from django.db.models import Q

from ..dtos import (
    ConfigDto,
    ServiceSnapshot,
    VolumeDto,
    EnvVariableDto,
    PortConfigurationDto,
    URLDto,
    HealthCheckDto,
    DockerCredentialsDto,
    DeploymentChangeDto,
    ResourceLimitsDto,
    GitAppDto,
    DockerfileBuilderOptions,
    StaticDirectoryBuilderOptions,
    NixpacksBuilderOptions,
)
from ..models import Service, DeploymentChange
from ..serializers import ServiceSerializer
from temporal.helpers import generate_caddyfile_for_static_website


def build_pending_changeset_with_extra(service: Service, change: dict | None = None):
    deployment_changes: list[DeploymentChangeDto] = []
    deployment_changes.extend(
        [
            DeploymentChangeDto.from_dict(
                dict(
                    type=ch.type,
                    field=ch.field,
                    new_value=ch.new_value,
                    old_value=ch.old_value,
                    item_id=ch.item_id,
                )
            )
            for ch in service.unapplied_changes.all()
        ]
    )
    if change is not None:
        deployment_changes.append(DeploymentChangeDto(**change))
    return deployment_changes


def apply_changes_to_snapshot(
    service_snapshot: ServiceSnapshot,
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
            case DeploymentChange.ChangeField.GIT_SOURCE:
                service_snapshot.repository_url = change.new_value["repository_url"]  # type: ignore
                service_snapshot.branch_name = change.new_value["branch_name"]  # type: ignore
                service_snapshot.commit_sha = change.new_value["commit_sha"]  # type: ignore
                gitapp: dict | None = change.new_value.get("git_app")  # type: ignore
                service_snapshot.git_app = (
                    GitAppDto.from_dict(gitapp) if gitapp is not None else None
                )
            case DeploymentChange.ChangeField.BUILDER:
                match change.new_value["builder"]:  # type: ignore
                    case Service.Builder.DOCKERFILE:
                        service_snapshot.builder = "DOCKERFILE"
                        service_snapshot.dockerfile_builder_options = (
                            DockerfileBuilderOptions.from_dict(
                                cast(dict, change.new_value)["options"]
                            )
                        )
                    case Service.Builder.STATIC_DIR:
                        service_snapshot.builder = "STATIC_DIR"
                        service_snapshot.static_dir_builder_options = (
                            StaticDirectoryBuilderOptions.from_dict(
                                cast(dict, change.new_value)["options"]
                            )
                        )
                    case Service.Builder.NIXPACKS:
                        service_snapshot.builder = "NIXPACKS"
                        service_snapshot.nixpacks_builder_options = (
                            NixpacksBuilderOptions.from_dict(
                                cast(dict, change.new_value)["options"]
                            )
                        )
                    case Service.Builder.RAILPACK:
                        service_snapshot.builder = "RAILPACK"
                        service_snapshot.railpack_builder_options = (
                            NixpacksBuilderOptions.from_dict(
                                cast(dict, change.new_value)["options"]
                            )
                        )
                    case _:
                        raise NotImplementedError(
                            f"This builder `{change.new_value.get('builder')}` type has not yet been implemented"  # type: ignore
                        )
                pass
            case DeploymentChange.ChangeField.RESOURCE_LIMITS:
                service_snapshot.resource_limits = (
                    ResourceLimitsDto.from_dict(change.new_value)
                    if change.new_value is not None
                    else None
                )
            case _:
                dto_class: type[
                    VolumeDto
                    | URLDto
                    | ConfigDto
                    | EnvVariableDto
                    | PortConfigurationDto
                ] = field_dto_map[change.field]  # type: ignore
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


def compute_snapshot_including_change(service: Service, change: dict | None = None):
    deployment_changes = build_pending_changeset_with_extra(service, change)

    service_snapshot = ServiceSnapshot.from_dict(
        ServiceSerializer(service).data  # type: ignore
    )
    return apply_changes_to_snapshot(service_snapshot, deployment_changes)


def compute_snapshot_excluding_change(service: Service, change_id: str):
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

    service_snapshot = ServiceSnapshot.from_dict(
        ServiceSerializer(service).data  # type: ignore
    )
    return apply_changes_to_snapshot(service_snapshot, deployment_changes)


def diff_service_snapshots(
    current: dict | ServiceSnapshot, target: dict | ServiceSnapshot
) -> list[DeploymentChange]:
    current_snapshot = (
        ServiceSnapshot.from_dict(current) if isinstance(current, dict) else current
    )
    target_snapshot = (
        ServiceSnapshot.from_dict(target) if isinstance(target, dict) else target
    )

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
            case "repository_url" | "branch_name" | "commit_sha" | "git_app":
                if current_value != target_value:
                    existing_change = next(
                        (
                            change
                            for change in changes
                            if change.field == DeploymentChange.ChangeField.GIT_SOURCE
                        ),
                        None,
                    )
                    if existing_change is None:
                        changes.append(
                            DeploymentChange(
                                type=DeploymentChange.ChangeType.UPDATE,
                                field=DeploymentChange.ChangeField.GIT_SOURCE,
                                new_value=dict(
                                    repository_url=target_snapshot.repository_url,
                                    branch_name=target_snapshot.branch_name,
                                    commit_sha=target_snapshot.commit_sha,
                                    git_app=(
                                        target_snapshot.git_app.to_dict()
                                        if target_snapshot.git_app is not None
                                        else None
                                    ),
                                ),
                                old_value=(
                                    dict(
                                        repository_url=current_snapshot.repository_url,
                                        branch_name=current_snapshot.branch_name,
                                        commit_sha=current_snapshot.commit_sha,
                                        git_app=(
                                            current_snapshot.git_app.to_dict()
                                            if current_snapshot.git_app is not None
                                            else None
                                        ),
                                    )
                                    if current_snapshot.repository_url is not None
                                    else None
                                ),
                            )
                        )

            case "dockerfile_builder_options" | "builder":
                if current_value != target_value:
                    existing_change = next(
                        (
                            change
                            for change in changes
                            if change.field == DeploymentChange.ChangeField.BUILDER
                        ),
                        None,
                    )
                    if existing_change is None:
                        new_value = {
                            "builder": target_snapshot.builder,
                        }
                        old_value = {
                            "builder": current_snapshot.builder,
                        }

                        match target_snapshot.builder:
                            case "DOCKERFILE":
                                new_value["options"] = (
                                    target_snapshot.dockerfile_builder_options.to_dict()
                                )  # type: ignore
                            case "STATIC_DIR":
                                new_value["options"] = (
                                    target_snapshot.static_dir_builder_options.to_dict()
                                )  # type: ignore
                                new_value["options"]["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        target_snapshot.static_dir_builder_options
                                    )
                                )  # type: ignore
                            case "NIXPACKS":
                                new_value["options"] = (
                                    target_snapshot.nixpacks_builder_options.to_dict()
                                )  # type: ignore
                                new_value["options"]["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        target_snapshot.nixpacks_builder_options
                                    )
                                    if target_snapshot.nixpacks_builder_options.is_static
                                    else None
                                )  # type: ignore
                            case "RAILPACK":
                                new_value["options"] = (
                                    target_snapshot.railpack_builder_options.to_dict()
                                )  # type: ignore
                                new_value["options"]["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        target_snapshot.railpack_builder_options
                                    )
                                    if target_snapshot.railpack_builder_options.is_static
                                    else None
                                )  # type: ignore
                            case _:
                                raise NotImplementedError(
                                    f"The builder `{target_snapshot.builder}` is not supported yet"
                                )
                        match current_snapshot.builder:
                            case "DOCKERFILE":
                                old_value["options"] = (
                                    current_snapshot.dockerfile_builder_options.to_dict()
                                )  # type: ignore
                            case "STATIC_DIR":
                                old_value["options"] = (
                                    current_snapshot.static_dir_builder_options.to_dict()
                                )  # type: ignore
                                old_value["options"]["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        current_snapshot.static_dir_builder_options
                                    )
                                )  # type: ignore
                            case "NIXPACKS":
                                old_value["options"] = (
                                    current_snapshot.nixpacks_builder_options.to_dict()
                                )  # type: ignore
                                old_value["options"]["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        target_snapshot.nixpacks_builder_options
                                    )
                                    if current_snapshot.nixpacks_builder_options.is_static
                                    else None
                                )  # type: ignore
                            case "RAILPACK":
                                old_value["options"] = (
                                    current_snapshot.railpack_builder_options.to_dict()
                                )  # type: ignore
                                old_value["options"]["generated_caddyfile"] = (
                                    generate_caddyfile_for_static_website(
                                        target_snapshot.railpack_builder_options
                                    )
                                    if current_snapshot.railpack_builder_options.is_static
                                    else None
                                )  # type: ignore
                            case _:
                                old_value = None

                        changes.append(
                            DeploymentChange(
                                type=DeploymentChange.ChangeType.UPDATE,
                                field=DeploymentChange.ChangeField.BUILDER,
                                new_value=new_value,
                                old_value=old_value,
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
