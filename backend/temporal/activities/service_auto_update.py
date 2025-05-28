from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import docker

from ..shared import UpdateDetails


docker_client: docker.DockerClient | None = None


def get_docker_client():
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


def is_image_updated(current_image: str, desired_image: str) -> bool:
    docker_client = get_docker_client()
    current_digest = docker_client.images.get_registry_data(current_image).id
    desired_digest = docker_client.images.get_registry_data(desired_image).id
    return current_digest != desired_digest


@activity.defn
async def update_docker_service(payload: UpdateDetails):
    docker_client = get_docker_client()
    service = docker_client.services.get(payload.service_name)
    current_image = service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
    new_image = payload.service_image + ":" + payload.desired_version
    if is_image_updated(current_image, new_image):
        print(
            f"Updating service '{payload.service_name}' to new image '{new_image}'..."
        )
        service.update(
            image=new_image,
        )
        print(f"Service '{payload.service_name}' updated and restarted successfully.")
    else:
        print(f"Service '{payload.service_name}' is already up-to-date.")


@activity.defn
async def update_image_version_in_env_file(new_version: str):
    lines = []
    env_file_path = "/app/.env"
    with open(env_file_path, "r") as file:
        for line in file:
            if line.startswith("IMAGE_VERSION="):
                lines.append(f"IMAGE_VERSION={new_version}\n")
            else:
                lines.append(line)
    with open(env_file_path, "w") as file:
        file.writelines(lines)

    print(f"Updated IMAGE_VERSION to {new_version}")
