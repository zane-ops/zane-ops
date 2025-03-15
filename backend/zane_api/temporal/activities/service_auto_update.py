import docker
from docker.errors import APIError, NotFound
from temporalio import activity

docker_client = docker.from_env()


# ==================================================
#    Docker Service Auto-Update 🐭
#
# - `get_service`: Retrieves a Docker service with error handling.
# - `is_image_updated`: Checks if the service image needs updating.
# - `update_service`: Updates the service, preserving configurations.
# - `update_image_version`: Syncs the .env file with the new IMAGE_VERSION.
# - `restart_service`: Restarts the service to apply .env changes.
# - `update_docker_service`: Main activity managing the update flow with logging.
# ==================================================


def get_service(service_name: str):
    try:
        return docker_client.services.get(service_name)
    except NotFound:
        raise ValueError(f"Service '{service_name}' not found.")
    except APIError as e:
        raise RuntimeError(f"Docker API error: {e}")


def is_image_updated(current_image: str, desired_image: str) -> bool:
    try:
        current_digest = docker_client.images.get_registry_data(current_image).id
        desired_digest = docker_client.images.get_registry_data(desired_image).id
        return current_digest != desired_digest
    except APIError as e:
        raise RuntimeError(f"Error comparing images: {e}")


def update_service(service, desired_image: str):
    try:
        service_spec = service.attrs["Spec"]
        task_template = service_spec["TaskTemplate"]
        container_spec = task_template["ContainerSpec"]

        service.update(
            image=desired_image,
            labels=service_spec.get("Labels"),
            networks=task_template.get("Networks"),
            mounts=container_spec.get("Mounts"),
            resources=task_template.get("Resources"),
            endpoint_spec=service_spec.get("EndpointSpec"),
            restart_policy=task_template.get("RestartPolicy"),
            mode=service_spec.get("Mode"),
            update_config=service_spec.get("UpdateConfig"),
        )
    except APIError as e:
        raise RuntimeError(f"Error updating service '{service.name}': {e}")


def update_image_version(new_version: str, env_file_path: str = "/app/.env"):
    lines = []
    with open(env_file_path, "r") as file:
        for line in file:
            if line.startswith("IMAGE_VERSION="):
                lines.append(f"IMAGE_VERSION={new_version}\n")
            else:
                lines.append(line)

    with open(env_file_path, "w") as file:
        file.writelines(lines)

    print(f"Updated IMAGE_VERSION to {new_version}")


def restart_service(service_name: str):
    service = get_service(service_name)
    service.update(force_update=True)
    print(f"Service {service_name} restarted to pick up new .env changes.")


@activity.defn
async def update_docker_service(service_name: str, desired_image: str):
    service = get_service(service_name)
    current_image = service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]

    if is_image_updated(current_image, desired_image):
        activity.logger.info(
            f"Updating service '{service_name}' to new image '{desired_image}'..."
        )
        update_service(service, desired_image)
        update_image_version(desired_image)
        restart_service(service_name)
        activity.logger.info(
            f"Service '{service_name}' updated and restarted successfully."
        )
    else:
        activity.logger.info(f"Service '{service_name}' is already up-to-date.")
