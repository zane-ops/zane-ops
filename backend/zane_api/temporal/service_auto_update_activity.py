import docker
from docker.errors import APIError, NotFound
from temporalio import activity

docker_client = docker.from_env()


# *****************************************
#  Note : get_service and is_image update
#  are helper functions
# *****************************************


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


def update_service(service, desired_image: str, desired_envs: list):
    try:
        service_spec = service.attrs["Spec"]
        task_template = service_spec["TaskTemplate"]
        container_spec = task_template["ContainerSpec"]

        service.update(
            image=desired_image,
            env=desired_envs,
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


@activity.defn
async def update_docker_service(
    service_name: str, desired_image: str, desired_envs: list
):
    service = get_service(service_name)
    current_image = service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]

    if is_image_updated(current_image, desired_image):
        activity.logger.info(
            f"Updating service '{service_name}' to new image '{desired_image}'..."
        )
        update_service(service, desired_image, desired_envs)
        activity.logger.info(f"Service '{service_name}' updated successfully.")
    else:
        activity.logger.info(f"Service '{service_name}' is already up-to-date.")
