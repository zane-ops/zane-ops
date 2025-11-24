import asyncio
from typing import Literal, Protocol, cast
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    import docker
    import docker.errors
    from zane_api.utils import Colors
    from zane_api.dtos import VolumeDto, ConfigDto
    from docker.types import (
        ConfigReference,
        NetworkAttachmentConfig,
        UpdateConfig,
        RestartPolicy,
        Healthcheck,
        Mount,
    )
    from django.conf import settings
    from ..helpers import get_docker_client, ZaneProxyClient

from ..shared import (
    DeleteSwarmRegistryDomainDetails,
    SwarmRegistryServiceDetails,
    DeleteSwarmRegistryServiceDetails,
    CreateBuildRegistryConfigsDetails,
    RegistrySnaphot,
)
from ..constants import (
    BUILD_REGISTRY_VOLUME_PATH,
    BUILD_REGISTRY_CONFIG_PATH,
    BUILD_REGISTRY_PASSWORD_PATH,
    BUILD_REGISTRY_IMAGE,
)
import platform
from zane_api.utils import DockerSwarmTask, DockerSwarmTaskState, find_item_in_sequence


class SimpleRegistryPayloadLike(Protocol):
    @property
    def swarm_service_name(self) -> str: ...


class DeployRegistryPayloadLike(Protocol):
    @property
    def swarm_service_name(self) -> str: ...

    @property
    def version(self) -> int: ...


def get_resource_labels(details: SimpleRegistryPayloadLike, **kwargs: str):
    return {"zane-managed": "true", "parent": details.swarm_service_name, **kwargs}


def get_volume_name_for_registry(
    details: DeployRegistryPayloadLike,
):
    return f"vol-{details.swarm_service_name}"


def get_config_name_for_registry(
    details: DeployRegistryPayloadLike,
    type: Literal["config", "credentials"],
):
    return f"cfg-{details.swarm_service_name}-{type}-v{details.version}"


@activity.defn
async def create_docker_volume_for_registry(payload: RegistrySnaphot):
    client = get_docker_client()
    print(
        f"Creating docker volume for registry {Colors.ORANGE}{payload.name}{Colors.ENDC}..."
    )
    volume = VolumeDto(
        mode="READ_WRITE",
        container_path=BUILD_REGISTRY_VOLUME_PATH,
        id=get_volume_name_for_registry(payload),
    )
    try:
        client.volumes.get(volume.id)  # type: ignore
    except docker.errors.NotFound:
        client.volumes.create(
            name=volume.id,  # type: ignore
            driver="local",
            labels=get_resource_labels(payload),
        )
    print(
        f"Volume created succesfully for registry {Colors.ORANGE}{payload.name}{Colors.ENDC}  ✅",
    )
    return volume


@activity.defn
async def pull_registry_image() -> bool:
    client = get_docker_client()
    print(
        f"Pulling image {Colors.ORANGE}{BUILD_REGISTRY_IMAGE}{Colors.ENDC}...",
    )
    try:
        client.images.pull(repository=BUILD_REGISTRY_IMAGE)
    except docker.errors.ImageNotFound:
        print(
            f"Error when pulling image {Colors.ORANGE}{BUILD_REGISTRY_IMAGE}{Colors.ENDC} {Colors.GREY}this image either does not exists for this platform (linux/{platform.machine()}) or may require authentication credentials to be pulled ❌{Colors.ENDC}",
        )
        return False
    except docker.errors.APIError as e:
        print(
            f"Error when pulling image {Colors.ORANGE}{BUILD_REGISTRY_IMAGE}{Colors.ENDC} {Colors.GREY}{e.explanation} ❌{Colors.ENDC}",
        )
        return False
    else:
        print(
            f"Finished pulling image {Colors.ORANGE}{BUILD_REGISTRY_IMAGE}{Colors.ENDC} ✅",
        )
        return True


@activity.defn
async def create_docker_configs_for_registry(
    payload: RegistrySnaphot,
) -> CreateBuildRegistryConfigsDetails:
    import bcrypt

    client = get_docker_client()
    print(
        f"Creating docker swarm configs for registry {Colors.ORANGE}{payload.name}{Colors.ENDC}..."
    )

    configFile = ConfigDto(
        mount_path=BUILD_REGISTRY_CONFIG_PATH,
        language="yaml",
        contents=payload.config.to_yaml(),
        id=get_config_name_for_registry(payload, type="config"),
    )

    print(f"[configFile] {configFile.id}.contents={configFile.contents}")

    try:
        client.configs.get(configFile.id)  # type: ignore
    except docker.errors.NotFound:
        client.configs.create(
            name=configFile.id,  # type: ignore
            labels=get_resource_labels(payload),
            data=configFile.contents.encode("utf-8"),
        )

    credentialsFile = ConfigDto(
        mount_path=BUILD_REGISTRY_PASSWORD_PATH,
        language="dotenv",
        contents=f"{payload.username}:{
            bcrypt.hashpw(
                payload.password.encode('utf-8'),
                bcrypt.gensalt(),
            ).decode('utf-8')
        }",
        id=get_config_name_for_registry(payload, type="credentials"),
    )
    print(f"[credentialsFile] {credentialsFile.id}.contents={credentialsFile.contents}")
    try:
        client.configs.get(credentialsFile.id)  # type: ignore
    except docker.errors.NotFound:
        client.configs.create(
            name=credentialsFile.id,  # type: ignore
            labels=get_resource_labels(payload),
            data=credentialsFile.contents.encode("utf-8"),
        )

    print(
        f"Swarm Configs created succesfully for registry {Colors.ORANGE}{payload.name}{Colors.ENDC}  ✅",
    )
    return CreateBuildRegistryConfigsDetails(configs=[configFile, credentialsFile])


@activity.defn
async def delete_previous_docker_configs_for_registry(
    registry: RegistrySnaphot,
):
    client = get_docker_client()
    print(
        f"Deleting previous configs for registry {Colors.ORANGE}{registry.swarm_service_name}(v{registry.version}){Colors.ENDC}..."
    )

    configFileId = get_config_name_for_registry(registry, type="config")
    credentialsFileId = get_config_name_for_registry(registry, type="credentials")

    try:
        config = client.configs.get(configFileId)
    except docker.errors.NotFound:
        pass  # the config has probably been deleted
    else:
        config.remove()

    try:
        config = client.configs.get(credentialsFileId)
    except docker.errors.NotFound:
        pass  # the config has probably been deleted
    else:
        config.remove()

    print(
        f"Succesfully deleted the Swarm Configs for registry {Colors.ORANGE}{registry.swarm_service_name}(v{registry.version}){Colors.ENDC}  ✅",
    )


@activity.defn
async def remove_service_registry_url(payload: DeleteSwarmRegistryDomainDetails):
    ZaneProxyClient.remove_build_registry_url(
        payload.service_alias,
    )


@activity.defn
async def cleanup_docker_registry_service_resources(
    payload: DeleteSwarmRegistryServiceDetails,
):
    client = get_docker_client()
    try:
        swarm_service = client.services.get(payload.swarm_service_name)
    except docker.errors.NotFound:
        print(f"service `{payload.swarm_service_name}` not found")
        # we will assume the service has already been deleted
        pass
    else:
        swarm_service.remove()

    async def wait_for_service_containers_to_be_removed():
        print(
            f"waiting for containers for service {payload.swarm_service_name=} to be removed..."
        )
        container_list = client.containers.list(
            filters={"name": payload.swarm_service_name}
        )
        while len(container_list) > 0:
            print(
                f"service {payload.swarm_service_name=} is not removed yet, "
                + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)
            container_list = client.containers.list(
                filters={"name": payload.swarm_service_name}
            )
            continue
        print(f"service {payload.swarm_service_name=} is removed, YAY !! 🎉")

    await wait_for_service_containers_to_be_removed()

    print("Removed service. YAY !! 🎉")
    print("deleting volume list...")
    docker_volume_list = client.volumes.list(
        filters={
            "label": [
                f"{key}={value}" for key, value in get_resource_labels(payload).items()
            ]
        }
    )

    for volume in docker_volume_list:
        volume.remove(force=True)
    print(f"Deleted {len(docker_volume_list)} volume(s), YAY !! 🎉")

    print("deleting config list...")
    docker_config_list = client.configs.list(
        filters={
            "label": [
                f"{key}={value}" for key, value in get_resource_labels(payload).items()
            ]
        }
    )

    for config in docker_config_list:
        config.remove()
    print(f"Deleted {len(docker_config_list)} config(s), YAY !! 🎉")


@activity.defn
async def upsert_registry_url_in_proxy(payload: RegistrySnaphot):
    ZaneProxyClient.upsert_registry_url(
        registry_id=payload.id,
        registry_alias=payload.service_alias,
        domain=payload.domain,
        is_secure=payload.is_secure,
    )


@activity.defn
async def update_build_registry_swarm_service(
    service: SwarmRegistryServiceDetails,
):
    client = get_docker_client()
    try:
        swarm_service = client.services.get(service.swarm_id)
    except docker.errors.NotFound:
        raise ApplicationError("This registry has not been deployed yet")
    else:
        # Volumes
        mounts: list[Mount] = []
        if service.volume is not None:
            mounts.append(
                Mount(
                    target=service.volume.container_path,
                    source=service.volume.id,
                    type="volume",
                )
            )

        # configs
        configs: list[ConfigReference] = []
        docker_config_list = client.configs.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(service.registry).items()
                ]
            }
        )
        for config in docker_config_list:
            config_id = cast(str, config.id)
            # do not include previous configs
            existing = service.configs.get(config.name)
            if existing is not None:
                configs.append(
                    ConfigReference(
                        config_id=config_id,
                        config_name=config.name,
                        filename=service.configs[config.name].mount_path,
                    )
                )

        print(
            f"Updating swarm service for registry {Colors.ORANGE}{service.registry.name}{Colors.ENDC}..."
        )
        swarm_service.update(
            image=BUILD_REGISTRY_IMAGE,
            mounts=mounts,
            labels=get_resource_labels(
                service.registry,
                type="registry",
                version=str(service.registry.version),
            ),
            env=[f"__ZANE_VERSION={service.registry.version}"],
            networks=[
                NetworkAttachmentConfig(
                    target="zane",
                    aliases=[
                        cast(str, service.alias),
                        cast(str, service.alias).replace(
                            f".{settings.ZANE_INTERNAL_DOMAIN}", ""
                        ),
                    ],
                ),
            ],
            update_config=UpdateConfig(
                order="start-first",
                parallelism=1,
            ),
            restart_policy=RestartPolicy(
                condition="any",
            ),
            healthcheck=Healthcheck(
                test=[
                    "CMD",
                    "wget",
                    "--quiet",
                    "--tries=1",
                    "--spider",
                    "http://localhost:5001/debug/health",
                ],
                # times are in nanoseconds, that's why they are mutiplied by `e9` (1 billion)
                interval=int(10e9),
                timeout=int(5e9),
                retries=3,
                start_period=int(5e9),
            ),
            stop_grace_period=int(30e9),
            configs=configs,
        )
        print(
            f"Succesfully updated swarm service for the registry {Colors.ORANGE}{service.registry.name}{Colors.ENDC} ✅",
        )


@activity.defn
async def wait_for_registry_service_to_be_updated(payload: RegistrySnaphot):
    client = get_docker_client()

    try:
        swarm_service = client.services.get(payload.swarm_service_name)
    except docker.errors.NotFound:
        raise ApplicationError("This registry has not been deployed yet")

    else:
        print(f"waiting for service {swarm_service.name=} to be updated...")

        current_service_task = DockerSwarmTask.from_dict(
            max(
                swarm_service.tasks(filters={"desired-state": "running"}),
                key=lambda task: task["Version"]["Index"],
            )
        )

        current_version_env = find_item_in_sequence(
            lambda env: env.startswith("__ZANE_VERSION"),
            current_service_task.Spec.ContainerSpec.Env,
        )

        _, current_version = cast(str, current_version_env).split("=")

        while (
            current_service_task.state != DockerSwarmTaskState.RUNNING
            and current_version != str(payload.version)
        ):
            print(
                f"service {swarm_service.name=} is not updated yet, "
                + f"retrying in {settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL} seconds..."
            )
            await asyncio.sleep(settings.DEFAULT_HEALTHCHECK_WAIT_INTERVAL)

            current_service_task = DockerSwarmTask.from_dict(
                max(
                    swarm_service.tasks(filters={"desired-state": "running"}),
                    key=lambda task: task["Version"]["Index"],
                )
            )
            current_version_env = find_item_in_sequence(
                lambda env: env.startswith("__ZANE_VERSION"),
                current_service_task.Spec.ContainerSpec.Env,
            )
            _, current_version = cast(str, current_version_env).split("=")
        print(f"service {swarm_service.name=} is updated, YAY !! 🎉")


@activity.defn
async def create_build_registry_swarm_service(
    service: SwarmRegistryServiceDetails,
):
    client = get_docker_client()

    try:
        client.services.get(service.swarm_id)
    except docker.errors.NotFound:
        # Volumes
        mounts: list[Mount] = []
        if service.volume is not None:
            mounts.append(
                Mount(
                    target=service.volume.container_path,
                    source=service.volume.id,
                    type="volume",
                )
            )

        # configs
        configs: list[ConfigReference] = []
        docker_config_list = client.configs.list(
            filters={
                "label": [
                    f"{key}={value}"
                    for key, value in get_resource_labels(service.registry).items()
                ]
            }
        )
        for config in docker_config_list:
            configs.append(
                ConfigReference(
                    config_id=cast(str, config.id),
                    config_name=config.name,
                    filename=service.configs[config.name].mount_path,
                )
            )

        print(
            f"Creating swarm service  for registry {Colors.ORANGE}{service.registry.name}{Colors.ENDC}..."
        )
        client.services.create(
            image=BUILD_REGISTRY_IMAGE,
            name=service.swarm_id,
            mounts=mounts,
            labels=get_resource_labels(
                service.registry,
                type="registry",
                version=str(service.registry.version),
            ),
            env=[f"__ZANE_VERSION={service.registry.version}"],
            networks=[
                NetworkAttachmentConfig(
                    target="zane",
                    aliases=[
                        cast(str, service.alias),
                        cast(str, service.alias).replace(
                            f".{settings.ZANE_INTERNAL_DOMAIN}", ""
                        ),
                    ],
                ),
            ],
            update_config=UpdateConfig(
                order="start-first",
                parallelism=1,
            ),
            restart_policy=RestartPolicy(
                condition="any",
            ),
            healthcheck=Healthcheck(
                test=[
                    "CMD",
                    "wget",
                    "--quiet",
                    "--tries=1",
                    "--spider",
                    "http://localhost:5001/debug/health",
                ],
                # times are in nanoseconds, that's why they are mutiplied by `e9` (1 billion)
                interval=int(10e9),
                timeout=int(5e9),
                retries=3,
                start_period=int(5e9),
            ),
            stop_grace_period=int(30e9),
            configs=configs,
        )
        print(
            f"Swarm service created succesfully for the registry {Colors.ORANGE}{service.registry.name}{Colors.ENDC} ✅",
        )
